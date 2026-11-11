from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.config.database import get_db
from app.models.database_models import User, UserRole, File, Project, Folder
from app.models.schemas import FileCreate, FileResponse, FileUpdate
from app.api.routes.auth import get_current_user
from sqlalchemy import or_
from app.services.gamification_service import GamificationService

router = APIRouter(prefix="/api/files", tags=["Files"])

@router.post("/", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
def create_file(
    file: FileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new file (root or project)."""
    
    # If project_id is provided, verify it belongs to user
    if file.project_id:
        project = db.query(Project).filter(
            Project.id == file.project_id,
            Project.user_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

    # If folder_id is provided, verify it exists + belongs to user + matches project scope
    if file.folder_id is not None:
        folder = db.query(Folder).filter(Folder.id == file.folder_id).first()
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")
        if folder.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to use this folder")
        if folder.project_id != file.project_id:
            raise HTTPException(status_code=400, detail="Folder scope mismatch")

    new_file = File(
        user_id=current_user.id,
        project_id=file.project_id,
        folder_id=file.folder_id,
        filename=file.filename,
        content=file.content,
        is_main=file.is_main,
        is_shared=file.is_shared
    )
    db.add(new_file)
    db.commit()
    db.refresh(new_file)
    
    # Award gamification XP
    try:
        GamificationService.award_xp(
            db=db,
            user_id=str(current_user.id),
            activity_type="circuit_saved",
            metadata={"filename": new_file.filename, "file_id": str(new_file.id)}
        )
    except Exception as e:
        # Don't fail the file operation if gamification fails
        pass
        
    return new_file

@router.get("/", response_model=List[FileResponse])
def get_files(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get files.
    - If project_id provided, return files in that project for current user.
    - If no project_id, return root files (project_id=None) for current user AND shared files.
    """
    query = db.query(File)
    
    if project_id:
        # Check project access first
        # Project must belong to user or be public? (Keeping simple: must belong to user for now)
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
             raise HTTPException(status_code=404, detail="Project not found")
        
        # Determine if user has access to project files
        # Allow if owner OR if project is public? 
        # User requirement: "can be shared file... if shared then visible to all user"
        # Since project level sharing was also requested, we should check project.is_public
        
        if project.user_id != current_user.id and not project.is_public:
             raise HTTPException(status_code=403, detail="Not authorized to view this project")

        return query.filter(File.project_id == project_id).all()
    else:
        # Root files request
        # Return user's root files OR files shared with them (global share)
        return query.filter(
            or_(
                # User's own root files
                (File.user_id == current_user.id) & (File.project_id == None),
                # Globally shared files (regardless of project?)
                # Requirement: "If it is shared then it will be visible to all user"
                # But we should probably only return SHARED ROOT files in this list,
                # or ALL shared files? listing ALL shared files in root might be messy.
                # Let's list User's root files + Shared Root files.
                 (File.is_shared == True) & (File.project_id == None)
            )
        ).all()

@router.get("/{file_id}", response_model=FileResponse)
def get_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific file by ID."""
    file = db.query(File).filter(File.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Access control
    # Owner always has access
    if file.user_id == current_user.id:
        return file
        
    # If shared, everyone has access
    if file.is_shared:
        return file
        
    # If in a public project, everyone has access
    if file.project and file.project.is_public:
        return file

    raise HTTPException(status_code=403, detail="Not authorized to access this file")

@router.put("/{file_id}", response_model=FileResponse)
def update_file(
    file_id: int,
    file_update: FileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a file."""
    file = db.query(File).filter(File.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # Only owner can update
    if file.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this file")

    if file_update.content is not None:
        file.content = file_update.content
    if file_update.filename is not None:
        file.filename = file_update.filename
    if file_update.is_main is not None:
        file.is_main = file_update.is_main
    if file_update.is_shared is not None:
         file.is_shared = file_update.is_shared
    if file_update.project_id is not None:
         # Moving file to a project (or removing from project if we allowed None, but schema handles Optional)
         # Verify project ownership if setting project_id
         project = db.query(Project).filter(
            Project.id == file_update.project_id, 
            Project.user_id == current_user.id
         ).first()
         if not project:
              raise HTTPException(status_code=404, detail="Target project not found")
         file.project_id = file_update.project_id
         # When moving between projects, clear folder association (folder scope changes)
         file.folder_id = None

    if file_update.folder_id is not None:
         # Assign/move to a folder
         folder = db.query(Folder).filter(Folder.id == file_update.folder_id).first()
         if not folder:
              raise HTTPException(status_code=404, detail="Folder not found")
         if folder.user_id != current_user.id:
              raise HTTPException(status_code=403, detail="Not authorized to use this folder")
         if folder.project_id != file.project_id:
              raise HTTPException(status_code=400, detail="Folder scope mismatch")
         file.folder_id = file_update.folder_id
         
    db.commit()
    db.refresh(file)
    
    # Award gamification XP for changing content
    if file_update.content is not None:
        try:
            GamificationService.award_xp(
                db=db,
                user_id=str(current_user.id),
                activity_type="circuit_saved",
                metadata={"filename": file.filename, "file_id": str(file.id)}
            )
        except Exception as e:
            pass
            
    return file

@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a file."""
    file = db.query(File).filter(File.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
            
    # Only the owner can delete. Ownerless (legacy) files may only be deleted by
    # an admin: previously ANY signed-in user could delete them.
    if file.user_id is None:
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Not authorized to delete this file")
    elif file.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this file")
        
    db.delete(file)
    db.commit()
