"""
Gamification service for XP tracking, level calculation, and achievements.

This service handles:
- XP awarding and tracking
- Level calculation and progression
- Activity logging
- User stats retrieval
- Achievement checking and unlocking
"""
from sqlalchemy.orm import Session
from app.models.gamification import UserGamification, GamificationActivity, Achievement, UserAchievement
from datetime import datetime, date
from typing import Dict, Any, Optional, List
import math
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# LEVEL PROGRESSION FORMULAS
# ============================================================================

def xp_for_level(level: int) -> int:
    """
    Calculate total XP required to reach a specific level.
    
    Formula: 500 * (level - 1)
    This creates a linear progression where each level requires 500 XP.
    
    Examples:
    - Level 1: 0 XP
    - Level 2: 500 XP
    - Level 3: 1000 XP
    - Level 10: 4500 XP
    
    Args:
        level: Target level (1-based)
        
    Returns:
        Total XP required to reach that level
    """
    if level <= 1:
        return 0
    return 500 * (level - 1)


def calculate_level(total_xp: int) -> int:
    """
    Calculate current level based on total XP.
    
    Constant time calculation for linear progression.
    
    Args:
        total_xp: Total XP accumulated
        
    Returns:
        Current level (minimum 1)
    """
    if total_xp <= 0:
        return 1
    
    # Linear formula inversion: level = (total_xp // 500) + 1
    return (total_xp // 500) + 1


# ============================================================================
# XP REWARD CONFIGURATION
# ============================================================================

# Base XP rewards for different activities
XP_REWARDS = {
    # Simulation activities
    'simulation_run': 10,
    'first_simulation': 50,  # First-time bonus

    # Conversion activities
    'conversion': 30,
    'first_conversion': 60,  # First-time bonus

    # Circuit management
    'circuit_saved': 5,
    'project_created': 25,

    # Learning activities
    'tutorial_completed': 100,
    'challenge_completed': 150,

    # Social activities
    'circuit_shared': 25,
    'helped_user': 50,

    # ── Circuit structural properties ────────────────────────────────────────
    # These are logged by the simulator route after QASM analysis.
    # Without entries here, award_xp() returns early and the activity is
    # never recorded, so achievement criteria can never be evaluated.
    'superposition_circuit': 15,
    'entangled_circuit': 20,

    # ── Named algorithm achievements ─────────────────────────────────────────
    'algorithm_deutsch': 50,
    'algorithm_grover': 75,
    'algorithm_shor': 100,
    'algorithm_vqe': 75,
    'algorithm_qaoa': 75,
    
    # ── Specialization Tracking ──────────────────────────────────────────────
    'qiskit_circuit': 5,
    'cirq_circuit': 5,
    'pennylane_circuit': 5,
}

# First-time bonus XP per activity type. (award_xp used to look up
# f"first_{activity_type}", i.e. "first_simulation_run", while the table only
# had "first_simulation", so the first-simulation bonus was never paid.)
FIRST_TIME_BONUS_KEYS = {
    'simulation_run': 'first_simulation',
    'conversion': 'first_conversion',
}


def first_time_bonus_xp(activity_type: str) -> Optional[int]:
    """XP to award instead of the base amount the first time a user does activity_type."""
    key = FIRST_TIME_BONUS_KEYS.get(activity_type, f'first_{activity_type}')
    return XP_REWARDS.get(key)



# ============================================================================
# GAMIFICATION SERVICE
# ============================================================================

class GamificationService:
    """Service for managing gamification features."""
    
    @staticmethod
    def get_or_create_stats(db: Session, user_id: str) -> UserGamification:
        """
        Get or create gamification stats for a user.
        
        Args:
            db: Database session
            user_id: User UUID as string
            
        Returns:
            UserGamification object
        """
        stats = db.query(UserGamification).filter(
            UserGamification.user_id == user_id
        ).first()
        
        if not stats:
            logger.info(f"Creating new gamification stats for user {user_id}")
            stats = UserGamification(user_id=user_id)
            db.add(stats)
            db.commit()
            db.refresh(stats)
        
        return stats
    
    @staticmethod
    def award_xp(
        db: Session,
        user_id: str,
        activity_type: str,
        xp_amount: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Award XP to a user for an activity.
        
        This is the core method for gamification. It:
        1. Determines XP amount (with first-time bonuses)
        2. Records the activity
        3. Updates user stats
        4. Calculates level progression
        5. Updates streaks
        6. Checks for newly unlocked achievements
        
        Args:
            db: Database session
            user_id: User UUID as string
            activity_type: Type of activity (e.g., 'simulation_run')
            xp_amount: Optional custom XP amount (overrides default)
            metadata: Optional additional data about the activity
            
        Returns:
            Dictionary with:
            - xp_gained: Amount of XP awarded
            - total_xp: New total XP
            - level: Current level
            - old_level: Previous level
            - level_up: Whether user leveled up
            - xp_to_next_level: XP needed for next level
            - new_achievements: List of newly unlocked achievements
        """
        try:
            # Get or create user stats
            stats = GamificationService.get_or_create_stats(db, user_id)
            
            # Determine XP amount
            if xp_amount is None:
                xp_amount = XP_REWARDS.get(activity_type, 0)
            
            # If no XP for this activity, return early
            if xp_amount <= 0:
                logger.warning(f"No XP defined for activity type: {activity_type}")
                return {
                    'xp_gained': 0,
                    'total_xp': stats.total_xp,
                    'level': stats.level,
                    'old_level': stats.level,
                    'level_up': False,
                    'xp_to_next_level': xp_for_level(stats.level + 1) - stats.total_xp,
                    'is_first_time': False,
                    'current_streak': stats.current_streak or 0,
                    'new_achievements': []
                }
            
            # Check for first-time bonus
            is_first_time = db.query(GamificationActivity).filter(
                GamificationActivity.user_id == user_id,
                GamificationActivity.activity_type == activity_type
            ).count() == 0
            
            # Apply first-time bonus if available
            if is_first_time:
                bonus = first_time_bonus_xp(activity_type)
                if bonus:
                    xp_amount = bonus
                    logger.info(f"First-time bonus applied for {activity_type}: {xp_amount} XP")
            
            # Record the activity
            activity = GamificationActivity(
                user_id=user_id,
                activity_type=activity_type,
                xp_awarded=xp_amount,
                activity_metadata=metadata or {}
            )
            db.add(activity)
            
            # Update user stats
            old_level = stats.level
            stats.total_xp += xp_amount
            stats.level = calculate_level(stats.total_xp)
            
            # Update streak
            today = date.today()
            if stats.last_activity_date:
                days_diff = (today - stats.last_activity_date).days
                if days_diff == 1:
                    # Consecutive day - increment streak
                    stats.current_streak += 1
                    if stats.current_streak > stats.longest_streak:
                        stats.longest_streak = stats.current_streak
                elif days_diff > 1:
                    # Streak broken - reset
                    stats.current_streak = 1
                # If days_diff == 0, same day - don't change streak
            else:
                # First activity ever
                stats.current_streak = 1
                stats.longest_streak = 1
            
            stats.last_activity_date = today
            stats.updated_at = datetime.utcnow()
            
            # Commit all changes before checking achievements
            db.commit()
            db.refresh(stats)
            
            level_up = stats.level > old_level
            
            if level_up:
                logger.info(f"User {user_id} leveled up: {old_level} -> {stats.level}")
            
            # Check for newly unlocked achievements
            new_achievements = GamificationService.check_achievements(
                db, user_id, activity_type
            )
            
            result = {
                'xp_gained': xp_amount,
                'total_xp': stats.total_xp,
                'level': stats.level,
                'old_level': old_level,
                'level_up': level_up,
                'xp_to_next_level': xp_for_level(stats.level + 1) - stats.total_xp,
                'is_first_time': is_first_time,
                'current_streak': stats.current_streak,
                'new_achievements': new_achievements
            }
            
            logger.info(f"Awarded {xp_amount} XP to user {user_id} for {activity_type}")
            return result
            
        except Exception as e:
            logger.error(f"Error awarding XP to user {user_id}: {e}")
            db.rollback()
            raise
    
    @staticmethod
    def get_user_stats(db: Session, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive gamification stats for a user.
        
        Args:
            db: Database session
            user_id: User UUID as string
            
        Returns:
            Dictionary with all user stats including:
            - user_id
            - total_xp
            - level
            - current_streak
            - longest_streak
            - xp_to_next_level
            - xp_current_level (XP threshold for current level)
            - xp_next_level (XP threshold for next level)
            - progress_percentage (% progress to next level)
        """
        stats = GamificationService.get_or_create_stats(db, user_id)
        
        xp_current_level = xp_for_level(stats.level)
        xp_next_level = xp_for_level(stats.level + 1)
        xp_to_next = xp_next_level - stats.total_xp
        
        # Calculate progress percentage within current level
        level_xp_range = xp_next_level - xp_current_level
        xp_in_current_level = stats.total_xp - xp_current_level
        progress_percentage = (xp_in_current_level / level_xp_range * 100) if level_xp_range > 0 else 0
        
        return {
            'user_id': str(stats.user_id),
            'total_xp': stats.total_xp,
            'level': stats.level,
            'current_streak': stats.current_streak,
            'longest_streak': stats.longest_streak,
            'last_activity_date': stats.last_activity_date.isoformat() if stats.last_activity_date else None,
            'xp_to_next_level': xp_to_next,
            'xp_current_level': xp_current_level,
            'xp_next_level': xp_next_level,
            'progress_percentage': round(progress_percentage, 1)
        }
    
    @staticmethod
    def get_recent_activities(
        db: Session,
        user_id: str,
        limit: int = 10
    ) -> list[Dict[str, Any]]:
        """
        Get recent activities for a user.
        
        Args:
            db: Database session
            user_id: User UUID as string
            limit: Maximum number of activities to return
            
        Returns:
            List of activity dictionaries
        """
        activities = db.query(GamificationActivity).filter(
            GamificationActivity.user_id == user_id
        ).order_by(
            GamificationActivity.created_at.desc()
        ).limit(limit).all()
        
        return [
            {
                'id': str(activity.id),
                'activity_type': activity.activity_type,
                'xp_awarded': activity.xp_awarded,
                'metadata': activity.activity_metadata,
                'created_at': f"{activity.created_at.isoformat()}Z"
            }
            for activity in activities
        ]
    
    @staticmethod
    def get_activity_summary(db: Session, user_id: str) -> Dict[str, Any]:
        """
        Get summary statistics of user activities.
        
        Args:
            db: Database session
            user_id: User UUID as string
            
        Returns:
            Dictionary with activity counts by type
        """
        from sqlalchemy import func
        
        results = db.query(
            GamificationActivity.activity_type,
            func.count(GamificationActivity.id).label('count'),
            func.sum(GamificationActivity.xp_awarded).label('total_xp')
        ).filter(
            GamificationActivity.user_id == user_id
        ).group_by(
            GamificationActivity.activity_type
        ).all()
        
        summary = {}
        for activity_type, count, total_xp in results:
            summary[activity_type] = {
                'count': count,
                'total_xp': total_xp or 0
            }
        
        return summary

    # ========================================================================
    # ACHIEVEMENT METHODS
    # ========================================================================

    @staticmethod
    def get_all_achievements(db: Session) -> List[Dict[str, Any]]:
        """
        Get all achievement definitions from the database.
        
        Returns:
            List of achievement dictionaries
        """
        achievements = db.query(Achievement).order_by(
            Achievement.category, Achievement.reward_xp
        ).all()
        
        return [
            {
                'id': str(a.id),
                'name': a.name,
                'description': a.description,
                'category': a.category,
                'criteria': a.criteria,
                'reward_xp': a.reward_xp,
                'rarity': a.rarity,
                'icon_name': a.icon_name,
                'is_hidden': a.is_hidden,
            }
            for a in achievements
        ]

    @staticmethod
    def get_user_achievements(
        db: Session,
        user_id: str,
        include_locked: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get achievements for a user, including progress and unlock status.
        
        Args:
            db: Database session
            user_id: User UUID as string
            include_locked: If True, include all achievements (locked + unlocked).
                            If False, only return unlocked achievements.
            
        Returns:
            List of achievement dictionaries with user progress
        """
        from sqlalchemy import func
        
        # Get all achievements
        all_achievements = db.query(Achievement).order_by(
            Achievement.category, Achievement.reward_xp
        ).all()
        
        # Get user's achievement records
        user_records = db.query(UserAchievement).filter(
            UserAchievement.user_id == user_id
        ).all()
        
        # Map achievement_id -> user record
        user_map = {str(ua.achievement_id): ua for ua in user_records}
        
        # Get activity counts for progress calculation
        activity_summary = GamificationService.get_activity_summary(db, user_id)
        
        # Get user stats for level/xp/streak checks
        stats = GamificationService.get_or_create_stats(db, user_id)
        
        result = []
        for achievement in all_achievements:
            aid = str(achievement.id)
            user_record = user_map.get(aid)
            
            is_unlocked = user_record is not None and user_record.unlocked_at is not None
            
            # Skip locked hidden achievements if not unlocked
            if achievement.is_hidden and not is_unlocked and not include_locked:
                continue
            
            # Calculate progress based on criteria
            progress, target = GamificationService._calculate_progress(
                achievement.criteria, activity_summary, stats
            )
            
            # If already unlocked, progress is always equal to target (100% complete)
            if is_unlocked:
                progress = target
            elif user_record and user_record.progress:
                # Not yet unlocked — use stored progress if it's higher than calculated
                stored_progress = user_record.progress.get('current', 0)
                progress = max(progress, stored_progress)
            
            entry = {
                'id': aid,
                'name': achievement.name if not (achievement.is_hidden and not is_unlocked) else "???",
                'description': achievement.description if not (achievement.is_hidden and not is_unlocked) else "This achievement is a secret!",
                'category': achievement.category,
                'rarity': achievement.rarity,
                'xp_reward': achievement.reward_xp,
                'icon_name': achievement.icon_name or 'award',
                'is_hidden': achievement.is_hidden,
                'is_unlocked': is_unlocked,
                'progress': progress if not (achievement.is_hidden and not is_unlocked) else 0,
                'target': target if not (achievement.is_hidden and not is_unlocked) else 1,
                'unlocked_at': user_record.unlocked_at.isoformat() + 'Z' if is_unlocked and user_record.unlocked_at else None,
            }
            
            if not include_locked and not is_unlocked:
                continue
            
            result.append(entry)
        
        return result

    @staticmethod
    def _calculate_progress(
        criteria: Dict[str, Any],
        activity_summary: Dict[str, Any],
        stats: UserGamification
    ) -> tuple:
        """
        Calculate current progress and target for an achievement.
        
        Args:
            criteria: Achievement criteria JSON
            activity_summary: User's activity counts
            stats: User gamification stats
            
        Returns:
            Tuple of (current_progress, target)
        """
        criteria_type = criteria.get('type', '')
        
        if criteria_type == 'activity_count':
            activity_type = criteria.get('activity_type', '')
            target = criteria.get('count', 1)
            current = activity_summary.get(activity_type, {}).get('count', 0)
            return (min(current, target), target)
        
        elif criteria_type == 'level_reached':
            target_level = criteria.get('level', 1)
            return (min(stats.level, target_level), target_level)
        
        elif criteria_type == 'streak_days':
            target_days = criteria.get('days', 1)
            current = max(stats.current_streak, stats.longest_streak)
            return (min(current, target_days), target_days)
        
        elif criteria_type == 'total_xp':
            target_xp = criteria.get('xp', 0)
            return (min(stats.total_xp, target_xp), target_xp)
        
        elif criteria_type == 'distinct_activity_count':
            # For distinct values, we can't easily count without metadata
            # Return 0 progress; actual checking done in check_achievements
            target = criteria.get('count', 1)
            return (0, target)
        
        elif criteria_type == 'multi_activity_count':
            activity_types = criteria.get('activity_types', [])
            target = criteria.get('count', 1)
            # Check that ALL activity types meet the minimum count
            min_count = float('inf')
            for act_type in activity_types:
                count = activity_summary.get(act_type, {}).get('count', 0)
                if count < min_count:
                    min_count = count
            current = min_count if min_count != float('inf') else 0
            return (min(current, target), target)
            
        elif criteria_type == 'multi_activity_threshold_count':
            activity_types = criteria.get('activity_types', [])
            threshold = criteria.get('threshold', 1)
            target = criteria.get('count', len(activity_types))
            
            met_count = sum(1 for act_type in activity_types if activity_summary.get(act_type, {}).get('count', 0) >= threshold)
            
            return (min(met_count, target), target)
        
        return (0, 1)

    @staticmethod
    def check_achievements(
        db: Session,
        user_id: str,
        activity_type: str
    ) -> List[Dict[str, Any]]:
        """
        Check and unlock any achievements the user has earned.
        
        Called after awarding XP to evaluate all relevant achievement criteria.
        
        Args:
            db: Database session
            user_id: User UUID as string
            activity_type: The activity that was just performed
            
        Returns:
            List of newly unlocked achievement dictionaries
        """
        try:
            # Get all achievements
            all_achievements = db.query(Achievement).all()
            
            # Get user's already-unlocked achievement IDs
            unlocked_ids = set()
            user_records = db.query(UserAchievement).filter(
                UserAchievement.user_id == user_id,
                UserAchievement.unlocked_at.isnot(None)
            ).all()
            for ur in user_records:
                unlocked_ids.add(str(ur.achievement_id))
            
            # Get activity summary and stats
            activity_summary = GamificationService.get_activity_summary(db, user_id)
            stats = GamificationService.get_or_create_stats(db, user_id)
            
            newly_unlocked = []
            
            for achievement in all_achievements:
                aid = str(achievement.id)
                
                # Skip already unlocked
                if aid in unlocked_ids:
                    continue
                
                # Evaluate criteria
                is_met = GamificationService._evaluate_criteria(
                    achievement.criteria, activity_summary, stats
                )
                
                if is_met:
                    # Unlock the achievement
                    unlocked = GamificationService._unlock_achievement(
                        db, user_id, achievement
                    )
                    if unlocked:
                        newly_unlocked.append(unlocked)
            
            return newly_unlocked
            
        except Exception as e:
            logger.error(f"Error checking achievements for user {user_id}: {e}")
            return []

    @staticmethod
    def _evaluate_criteria(
        criteria: Dict[str, Any],
        activity_summary: Dict[str, Any],
        stats: UserGamification
    ) -> bool:
        """
        Evaluate whether achievement criteria are met.
        
        Args:
            criteria: Achievement criteria JSON
            activity_summary: User's activity counts
            stats: User gamification stats
            
        Returns:
            True if criteria are met
        """
        criteria_type = criteria.get('type', '')
        
        if criteria_type == 'activity_count':
            activity_type = criteria.get('activity_type', '')
            required_count = criteria.get('count', 1)
            current_count = activity_summary.get(activity_type, {}).get('count', 0)
            return current_count >= required_count
        
        elif criteria_type == 'level_reached':
            required_level = criteria.get('level', 1)
            return stats.level >= required_level
        
        elif criteria_type == 'streak_days':
            required_days = criteria.get('days', 1)
            best_streak = max(stats.current_streak, stats.longest_streak)
            return best_streak >= required_days
        
        elif criteria_type == 'total_xp':
            required_xp = criteria.get('xp', 0)
            return stats.total_xp >= required_xp
        
        elif criteria_type == 'distinct_activity_count':
            # For now, count based on activity count as approximation
            activity_type = criteria.get('activity_type', '')
            required_count = criteria.get('count', 1)
            current_count = activity_summary.get(activity_type, {}).get('count', 0)
            return current_count >= required_count
        
        elif criteria_type == 'multi_activity_count':
            activity_types = criteria.get('activity_types', [])
            required_count = criteria.get('count', 1)
            for act_type in activity_types:
                count = activity_summary.get(act_type, {}).get('count', 0)
                if count < required_count:
                    return False
            return True
            
        elif criteria_type == 'multi_activity_threshold_count':
            activity_types = criteria.get('activity_types', [])
            threshold = criteria.get('threshold', 1)
            required_count = criteria.get('count', len(activity_types))
            
            met_count = sum(1 for act_type in activity_types if activity_summary.get(act_type, {}).get('count', 0) >= threshold)
            return met_count >= required_count
        
        return False

    @staticmethod
    def _unlock_achievement(
        db: Session,
        user_id: str,
        achievement: Achievement
    ) -> Optional[Dict[str, Any]]:
        """
        Unlock an achievement for a user and award bonus XP.
        
        Args:
            db: Database session
            user_id: User UUID as string
            achievement: Achievement model instance
            
        Returns:
            Achievement dict if newly unlocked, None otherwise
        """
        try:
            aid = str(achievement.id)
            
            # Check if already has a record
            existing = db.query(UserAchievement).filter(
                UserAchievement.user_id == user_id,
                UserAchievement.achievement_id == achievement.id
            ).first()
            
            now = datetime.utcnow()
            
            # Determine the correct target from the achievement criteria
            criteria = achievement.criteria or {}
            criteria_type = criteria.get('type', '')
            if criteria_type == 'activity_count':
                unlock_target = criteria.get('count', 1)
            elif criteria_type == 'level_reached':
                unlock_target = criteria.get('level', 1)
            elif criteria_type == 'streak_days':
                unlock_target = criteria.get('days', 1)
            elif criteria_type == 'total_xp':
                unlock_target = criteria.get('xp', 1)
            elif criteria_type == 'distinct_activity_count':
                unlock_target = criteria.get('count', 1)
            elif criteria_type == 'multi_activity_count':
                unlock_target = criteria.get('count', 1)
            elif criteria_type == 'multi_activity_threshold_count':
                unlock_target = criteria.get('count', 1)
            else:
                unlock_target = 1

            if existing:
                if existing.unlocked_at:
                    # Already unlocked
                    return None
                # Update existing record
                existing.unlocked_at = now
                existing.progress = {"current": unlock_target, "target": unlock_target}
            else:
                # Create new record
                user_achievement = UserAchievement(
                    user_id=user_id,
                    achievement_id=achievement.id,
                    progress={"current": unlock_target, "target": unlock_target},
                    unlocked_at=now
                )
                db.add(user_achievement)
            
            # Award bonus XP for the achievement (without recursive achievement check)
            if achievement.reward_xp > 0:
                stats = GamificationService.get_or_create_stats(db, user_id)
                stats.total_xp += achievement.reward_xp
                stats.level = calculate_level(stats.total_xp)
                stats.updated_at = now
                
                # Log achievement XP as activity
                activity = GamificationActivity(
                    user_id=user_id,
                    activity_type='achievement_unlocked',
                    xp_awarded=achievement.reward_xp,
                    activity_metadata={
                        'achievement_name': achievement.name,
                        'achievement_id': aid
                    }
                )
                db.add(activity)
            
            db.commit()
            
            logger.info(f"User {user_id} unlocked achievement: {achievement.name} (+{achievement.reward_xp} XP)")
            
            return {
                'id': aid,
                'name': achievement.name,
                'description': achievement.description,
                'category': achievement.category,
                'rarity': achievement.rarity,
                'xp_reward': achievement.reward_xp,
                'icon_name': achievement.icon_name or 'award',
                'unlocked_at': now.isoformat() + 'Z',
            }
            
        except Exception as e:
            logger.error(f"Error unlocking achievement {achievement.name} for user {user_id}: {e}")
            db.rollback()
            return None
