# QCanvas Technical Context

## Technologies Used

### Backend Stack
- **Python 3.8+**: Core programming language
- **FastAPI**: Modern, fast web framework for building APIs
- **Uvicorn**: ASGI server for running FastAPI applications
- **Pydantic**: Data validation using Python type annotations
- **SQLAlchemy**: SQL toolkit and Object-Relational Mapping (ORM)
- **Redis**: In-memory data structure store for caching and sessions
- **PostgreSQL**: Primary database for persistent storage

### Frontend Stack
- **Next.js 14+**: React framework with App Router
- **React 18+**: JavaScript library for building user interfaces
- **TypeScript**: Typed superset of JavaScript for type safety
- **Tailwind CSS**: Utility-first CSS framework for styling
- **Monaco Editor**: Advanced code editor with syntax highlighting
- **Chart.js**: Data visualization for histograms and charts
- **Lucide React**: Modern icon library
- **React Hot Toast**: Notification system
- **Zustand**: State management library
- **WebSocket**: Real-time communication protocol

### Quantum Computing Frameworks
- **Cirq**: Google's quantum computing framework
- **Qiskit**: IBM's quantum computing framework
- **PennyLane**: Xanadu's quantum machine learning framework
- **OpenQASM 3.0**: Open Quantum Assembly Language standard (universal IR; “Rosetta Stone”)

### DevOps and Deployment
- **Docker**: Containerization platform
- **Docker Compose**: Multi-container application orchestration
- **Nginx**: Web server and reverse proxy
- **Prometheus**: Metrics collection and monitoring
- **Grafana**: Metrics visualization and dashboards

### User Experience Features
- **Authentication**: Persistent login with localStorage, demo accounts
- **Keyboard Shortcuts**: Comprehensive shortcut system with 10+ commands
- **Settings Management**: Theme selection, auto-save, format preferences
- **Example System**: 25+ pre-built quantum examples across all frameworks
  - Algorithms: Teleportation, Deutsch-Jozsa, QRNG, Grover's, XOR, QML XOR Classifier
  - Categories: Basic Circuits, Quantum Algorithms, Variational Algorithms, Error Correction, Quantum Machine Learning
  - All three frameworks (Cirq, Qiskit, PennyLane) represented
- **File Templates**: Separate from initial files for maximum variety
  - Initial files: Bell (Cirq), Deutsch-Jozsa (Qiskit), Grover's (PennyLane)
  - Templates: Teleportation (Qiskit), QRNG (Cirq), XOR Demo (PennyLane), QML XOR (PennyLane)
- **Responsive Design**: Mobile-first approach with adaptive layouts
- **Real-time Feedback**: Toast notifications and progress indicators
- **Modal Interactions**: Click-outside-to-close behavior for all modals

## Development Setup

### Prerequisites
- Python 3.8 or higher
- Node.js 18 or higher
- Docker and Docker Compose (optional)
- Git for version control

### Environment Setup
```bash
# Clone repository
git clone https://github.com/your-username/qcanvas.git
cd qcanvas

# --- Option 1: Linux helper scripts (recommended on Linux) ---

# First-time installation: system packages, Python venv, backend + frontend deps
bash setup.sh

# Environment configuration
cp environment.env.example environment.env
# Edit environment.env with your settings

# Start/stop services in background (Next.js + FastAPI)
./run.sh start   # starts backend + frontend in background, writes logs/frontend.log and logs/backend.log
./run.sh stop    # stops node/next/uvicorn processes and clears PID files

# --- Option 2: Manual setup (all platforms, including Windows) ---

# Python environment
python -m venv qasm_env
source qasm_env/bin/activate  # On Windows: qasm_env\Scripts\activate
pip install -r requirements.txt

# Frontend dependencies
cd frontend
npm install
cd ..

# Environment configuration (if not already done)
cp environment.env.example environment.env
# Edit environment.env with your settings
```

### Development Servers
```bash
# Backend (Terminal 1)
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000  # exposes /api/converter/* and /api/simulator/* (QSim)

# Frontend (Terminal 2)
cd ../frontend
npm run dev
```

### Docker Development
```bash
# Build and run all services
docker-compose up --build

# Access services
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Technical Constraints

### Performance Requirements
- API response time: <2 seconds for simple operations
- Simulation time: <30 seconds for circuits up to 20 qubits
- WebSocket latency: <100ms for real-time updates
- Memory usage: <4GB for typical operations

### Scalability Considerations
- Support for 100+ concurrent users
- Horizontal scaling via Docker containers
- Database connection pooling
- Redis clustering for high availability

### Security Requirements
- Input validation on all endpoints
- Rate limiting to prevent abuse
- CORS configuration for cross-origin requests
- Secure WebSocket connections (WSS in production)
- Environment variable management for secrets

### Browser Compatibility
- Modern browsers (Chrome 90+, Firefox 88+, Safari 14+, Edge 90+)
- WebSocket support required
- JavaScript ES2020+ features
- CSS Grid and Flexbox support

## Dependencies

### Python Dependencies (requirements.txt)
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
sqlalchemy==2.0.23
redis==5.0.1
psycopg2-binary==2.9.9
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-dotenv==1.0.0

# Quantum computing frameworks
cirq==1.2.0
qiskit==0.45.0
pennylane==0.34.0

# Scientific computing
numpy==1.24.3
scipy==1.11.4
matplotlib==3.7.2

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
httpx==0.25.2
```

### Node.js Dependencies (package.json)
```json
{
  "dependencies": {
    "next": "14.0.0",
    "react": "18.2.0",
    "react-dom": "18.2.0",
    "typescript": "5.2.2",
    "tailwindcss": "3.3.5",
    "autoprefixer": "10.4.16",
    "postcss": "8.4.31"
  },
  "devDependencies": {
    "@types/node": "20.8.0",
    "@types/react": "18.2.25",
    "@types/react-dom": "18.2.11",
    "eslint": "8.51.0",
    "eslint-config-next": "14.0.0"
  }
}
```

## Configuration Management

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/qcanvas
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# API Configuration
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ORIGINS=http://localhost:3000

# Quantum Simulation Limits
MAX_QUBITS=20
MAX_SHOTS=10000
SIMULATION_TIMEOUT=30

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### Docker Configuration
```yaml
# docker-compose.yml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: qcanvas
      POSTGRES_USER: qcanvas
      POSTGRES_PASSWORD: qcanvas
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://qcanvas:qcanvas@postgres:5432/qcanvas
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - backend
```

## Development Tools

### Code Quality Tools
- **Black**: Python code formatter
- **Flake8**: Python linting
- **MyPy**: Python type checking
- **ESLint**: JavaScript/TypeScript linting
- **Prettier**: Code formatting

### Testing Tools
- **pytest**: Python testing framework
- **Jest**: JavaScript testing framework
- **Cypress**: End-to-end testing
- **Coverage.py**: Python code coverage
- **Istanbul**: JavaScript code coverage

### Development Workflow
```bash
# Code formatting
black backend/
npm run format

# Linting
flake8 backend/
npm run lint

# Type checking
mypy backend/
npm run type-check

# Testing
pytest tests/
npm test

# Coverage
pytest --cov=backend --cov-report=html
npm run test:coverage
```

## Deployment Architecture

### Production Environment
- **Load Balancer**: Nginx reverse proxy
- **Application Servers**: Multiple FastAPI instances
- **Database**: PostgreSQL with read replicas
- **Cache**: Redis cluster
- **Monitoring**: Prometheus + Grafana
- **Logging**: Structured JSON logs

### Container Strategy
- Multi-stage Docker builds for optimization
- Non-root users for security
- Health checks for all services
- Resource limits and requests
- Secrets management via environment variables

### CI/CD Pipeline
1. **Code Quality**: Linting, formatting, type checking
2. **Testing**: Unit, integration, and e2e tests
3. **Security**: Dependency scanning, vulnerability checks
4. **Build**: Docker image creation and registry push
5. **Deploy**: Rolling deployment to production
6. **Monitor**: Health checks and performance monitoring

## Performance Optimization

### Backend Optimizations
- Async/await for I/O operations
- Connection pooling for database
- Redis caching for frequent operations
- Circuit optimization algorithms
- Resource limits and timeouts

### Frontend Optimizations
- Next.js App Router for optimal routing
- Server-side rendering for SEO
- Static site generation for static content
- Code splitting and lazy loading
- Image optimization and compression

### Database Optimizations
- Proper indexing for query performance
- Connection pooling and prepared statements
- Read replicas for scaling reads
- Query optimization and monitoring
- Regular maintenance and cleanup

## Monitoring and Observability

### Metrics Collection
- Application performance metrics
- Quantum simulation metrics
- User interaction metrics
- System resource utilization
- Error rates and response times

### Logging Strategy
- Structured JSON logging
- Different log levels (DEBUG, INFO, WARNING, ERROR)
- Request/response logging
- Quantum operation logging
- Performance metrics logging

### Alerting
- High error rates
- Performance degradation
- Resource exhaustion
- Security incidents
- Service availability issues
