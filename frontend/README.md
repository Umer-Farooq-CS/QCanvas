# QCanvas - Quantum Code Editor

A Next.js 14 quantum circuit code editor with TypeScript, App Router, and Tailwind CSS.

## Features

- 🚀 **Next.js 14** with App Router
- 📝 **Monaco Editor** for quantum code editing
- 🗂️ **File Management** with Zustand state management
- 🎨 **Tailwind CSS** with quantum-themed design
- 📱 **Responsive** desktop-first layout
- 🔐 **Mock Authentication** system ready for integration

## Tech Stack

- **Framework**: Next.js 14 + TypeScript
- **Styling**: Tailwind CSS
- **Editor**: Monaco Editor
- **State**: Zustand
- **UI**: Custom components with Lucide icons
- **Notifications**: React Hot Toast

## Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Installation

1. Clone the repository:
```bash
git clone <your-repo>
cd qcanvas-nextjs
```

2. Install dependencies:
```bash
npm install
```

3. Copy environment variables:
```bash
cp .env.example .env.local
```

4. Start the development server:
```bash
npm run dev
```

5. Open [http://localhost:3000](http://localhost:3000) in your browser.

### Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint
- `npm run type-check` - Run TypeScript checks

## Project Structure

```
app/
  (auth)/login/page.tsx          # Login page
  (app)/                         # Protected app routes
    layout.tsx                   # App layout with TopBar/Sidebar
    page.tsx                     # Main editor page
  api/                           # API routes
    health/route.ts              # Health check
    files/route.ts               # File CRUD operations
    files/[id]/route.ts          # Individual file operations
  globals.css                    # Global styles
  layout.tsx                     # Root layout
components/                      # Reusable components
  TopBar.tsx                     # Action buttons and theme toggle
  Sidebar.tsx                    # File tree and management
  EditorPane.tsx                 # Monaco editor integration
  ResultsPane.tsx                # Console-like results panel
lib/                            # Utilities
  store.ts                       # Zustand state management
  api.ts                         # API helper functions
  utils.ts                       # Utility functions
types/
  index.ts                       # TypeScript type definitions
```

## Features Overview

### File Management
- Create, edit, delete, and rename quantum code files
- Support for multiple file types (Python, QASM, etc.)
- File tree navigation in sidebar

### Code Editor
- Monaco Editor with syntax highlighting
- Quantum code editing support
- Auto-save functionality
- Keyboard shortcuts (Ctrl/Cmd+S to save)

### Mock API
All API endpoints return mock data for development:
- `GET /api/files` - List all files
- `GET /api/files/[id]` - Get specific file
- `POST /api/files` - Create new file
- `PUT /api/files/[id]` - Update file content
- `GET /api/health` - Health check

### Authentication (Mock)
- Login page with email/password form
- Protected routes (UI-only protection)
- Ready for NextAuth integration

## Development Notes

- **Mock Data**: All file operations use mock data stored in Zustand
- **No Database**: Everything is in-memory for now
- **No Real Auth**: Login is UI-only, ready for backend integration
- **Responsive**: Desktop-first design, mobile-friendly
- **Type Safe**: Full TypeScript coverage

## Next Steps

This scaffold is ready for:
1. FastAPI backend integration
2. Real authentication with NextAuth
3. Database persistence
4. Quantum execution engine
5. Real-time collaboration

## Contributing

1. Follow the existing code structure
2. Use TypeScript for all new code
3. Follow the component patterns in `/components`
4. Test mock APIs before real backend integration

## License

Open Quantum Workbench Proprietary License. See the LICENSE file in the repository root.
