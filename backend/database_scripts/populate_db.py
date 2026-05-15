
import os
import sys
import uuid
import random
from datetime import datetime, timedelta, date

# Add backend directory to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.config.database import SessionLocal
from app.models.database_models import (
    User, Project, File, Job, Conversion, ConversionStats, 
    Simulation, Session, ApiActivity, SharedSnippet,
    UserRole, QuantumFramework, SimulationBackend, 
    ExecutionStatus, SessionType, JobStatus
)
from app.models.gamification import (
    UserGamification, GamificationActivity, Achievement, UserAchievement
)
from app.utils.security import SecurityUtils


# ──────────────────────────────────────────────────────────
# Sample quantum code snippets for realistic dummy data
# ──────────────────────────────────────────────────────────
SAMPLE_CODES = {
    "cirq": """import cirq

q0, q1 = cirq.LineQubit.range(2)
circuit = cirq.Circuit(
    cirq.H(q0),
    cirq.CNOT(q0, q1),
    cirq.measure(q0, q1)
)
print(circuit)
""",
    "qiskit": """from qiskit import QuantumCircuit

qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])
print(qc)
""",
    "pennylane": """import pennylane as qml

dev = qml.device("default.qubit", wires=2)

@qml.qnode(dev)
def bell_state():
    qml.Hadamard(wires=0)
    qml.CNOT(wires=[0, 1])
    return qml.probs(wires=[0, 1])

print(bell_state())
""",
}

SAMPLE_QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\nh q[0];\ncx q[0],q[1];\nmeasure q -> c;'

# Achievement definitions matching the gamification system
ACHIEVEMENTS = [
    {"name": "First Circuit", "description": "Run your first quantum circuit", "category": "getting_started", "criteria": {"type": "simulation_count", "target": 1}, "reward_xp": 50, "rarity": "common", "icon_name": "Zap"},
    {"name": "Hello Quantum", "description": "Complete your first conversion", "category": "getting_started", "criteria": {"type": "conversion_count", "target": 1}, "reward_xp": 50, "rarity": "common", "icon_name": "Code"},
    {"name": "Circuit Builder", "description": "Run 10 simulations", "category": "progression", "criteria": {"type": "simulation_count", "target": 10}, "reward_xp": 200, "rarity": "uncommon", "icon_name": "Cpu"},
    {"name": "Polyglot", "description": "Use all 3 quantum frameworks", "category": "mastery", "criteria": {"type": "frameworks_used", "target": 3}, "reward_xp": 300, "rarity": "rare", "icon_name": "Globe"},
    {"name": "Streak Master", "description": "Maintain a 7-day activity streak", "category": "progression", "criteria": {"type": "streak", "target": 7}, "reward_xp": 500, "rarity": "epic", "icon_name": "Flame"},
    {"name": "Quantum Sage", "description": "Reach level 10", "category": "mastery", "criteria": {"type": "level", "target": 10}, "reward_xp": 1000, "rarity": "legendary", "icon_name": "Crown"},
    {"name": "Community Contributor", "description": "Share 3 projects with the community", "category": "social", "criteria": {"type": "shared_count", "target": 3}, "reward_xp": 250, "rarity": "uncommon", "icon_name": "Share2"},
    {"name": "Deep Dive", "description": "Run a simulation with 4096+ shots", "category": "mastery", "criteria": {"type": "max_shots", "target": 4096}, "reward_xp": 150, "rarity": "uncommon", "icon_name": "Target"},
]

SHARED_TAGS = [
    "quantum-circuits,qubits,superposition",
    "entanglement,bell-state,measurement",
    "grover,quantum-algorithms,search",
    "hadamard,pauli-x,cnot",
    "vqc,quantum-machine-learning,hybrid-quantum-classical",
    "circuit-optimization,depth-optimization,noise-aware",
]

CATEGORIES = ["Basic Circuits", "Algorithms", "Quantum ML", "Cryptography", "Error Correction"]
DIFFICULTIES = ["beginner", "intermediate", "advanced"]
FRAMEWORKS = ["cirq", "qiskit", "pennylane"]

USER_BIOS = [
    "Quantum computing researcher focused on NISQ-era algorithms.",
    "CS student exploring quantum information science.",
    "Full-stack developer diving into quantum programming.",
    None, # Some users don't have bios
    "Physics PhD candidate working on quantum error correction.",
]


def populate_dummy_data():
    db = SessionLocal()
    try:
        print("Starting to populate database with dummy data...\n")
        
        # ────────────────────────────
        # 1. USERS
        # ────────────────────────────
        print("👤 Creating Users...")
        users = []
        user_data = [
            ("admin@qcanvas.com", "admin", "Admin User", UserRole.ADMIN),
            ("alice@example.com", "alice_q", "Alice Quantum", UserRole.USER),
            ("bob@example.com", "bob_circuits", "Bob Circuit", UserRole.USER),
            ("charlie@example.com", "charlie_sim", "Charlie Simulator", UserRole.USER),
            ("diana@example.com", "diana_ml", "Diana ML", UserRole.USER),
        ]
        
        for i, (email, username, full_name, role) in enumerate(user_data):
            user = User(
                email=email,
                username=username,
                full_name=full_name,
                bio=USER_BIOS[i],
                role=role,
                is_active=True,
                is_verified=True,
                created_at=datetime.utcnow() - timedelta(days=random.randint(10, 60))
            )
            user.set_password("password123")
            db.add(user)
            users.append(user)
        
        db.commit()
        for u in users:
            db.refresh(u)
        print(f"   ✅ Created {len(users)} users")
            
        # ────────────────────────────
        # 2. PROJECTS
        # ────────────────────────────
        print("📁 Creating Projects...")
        projects = []
        project_names = [
            "Bell State Experiments", "Grover's Search Implementation",
            "Quantum ML Playground", "Error Correction Tests",
            "Teleportation Protocol", "VQE Optimizer"
        ]
        
        for i, name in enumerate(project_names):
            owner = users[i % len(users)]
            project = Project(
                user_id=owner.id,
                name=name,
                description=f"A quantum computing project exploring {name.lower()}.",
                is_public=random.choice([True, False]),
                created_at=datetime.utcnow() - timedelta(days=random.randint(1, 30))
            )
            db.add(project)
            projects.append(project)
            
        db.commit()
        for p in projects:
            db.refresh(p)
        print(f"   ✅ Created {len(projects)} projects")
            
        # ────────────────────────────
        # 3. FILES
        # ────────────────────────────
        print("📄 Creating Files...")
        files = []
        for i, project in enumerate(projects):
            fw = FRAMEWORKS[i % len(FRAMEWORKS)]
            code = SAMPLE_CODES[fw]
            
            file = File(
                user_id=project.user_id,
                project_id=project.id,
                filename=f"{project.name.lower().replace(' ', '_')}.py",
                content=code,
                is_main=True,
                is_shared=project.is_public
            )
            db.add(file)
            files.append(file)
        
        # Add some standalone user files (not in projects)
        for i, user in enumerate(users[:3]):
            fw = FRAMEWORKS[i % len(FRAMEWORKS)]
            file = File(
                user_id=user.id,
                project_id=None,
                filename=f"scratch_{user.username}.py",
                content=SAMPLE_CODES[fw],
                is_main=False,
                is_shared=False
            )
            db.add(file)
            files.append(file)
            
        db.commit()
        print(f"   ✅ Created {len(files)} files")
        
        # ────────────────────────────
        # 4. JOBS
        # ────────────────────────────
        print("⚙️  Creating Jobs...")
        job_count = 0
        for i in range(8):
            user = random.choice(users)
            project = random.choice(projects)
            status = random.choice(list(JobStatus))
            job = Job(
                user_id=user.id,
                project_id=project.id,
                status=status,
                backend=random.choice(["aer_simulator", "ibmq_qasm_simulator", "cirq_simulator"]),
                shots=random.choice([128, 512, 1024, 2048, 4096]),
                execution_time_ms=random.randint(100, 5000) if status in [JobStatus.COMPLETED] else None,
                created_at=datetime.utcnow() - timedelta(hours=random.randint(1, 72))
            )
            db.add(job)
            job_count += 1
        print(f"   ✅ Created {job_count} jobs")
            
        # ────────────────────────────
        # 5. CONVERSIONS + STATS
        # ────────────────────────────
        print("🔄 Creating Conversions...")
        conv_count = 0
        for i in range(10):
            user = random.choice(users)
            status = random.choice(list(ExecutionStatus))
            source_fw = random.choice(list(QuantumFramework))
            target_fw = random.choice([f for f in list(QuantumFramework) if f != source_fw])
            
            conversion = Conversion(
                user_id=user.id,
                source_framework=source_fw,
                target_framework=target_fw,
                source_code=SAMPLE_CODES.get(source_fw.value, "# source code"),
                target_code=SAMPLE_CODES.get(target_fw.value, "# target code") if status == ExecutionStatus.SUCCESS else None,
                qasm_code=SAMPLE_QASM if status == ExecutionStatus.SUCCESS else None,
                status=status,
                execution_time_ms=random.randint(50, 1000) if status == ExecutionStatus.SUCCESS else None,
                error_message="Conversion timeout" if status == ExecutionStatus.FAILED else None
            )
            db.add(conversion)
            db.flush()
            
            if status == ExecutionStatus.SUCCESS:
                stats = ConversionStats(
                    conversion_id=conversion.id,
                    num_qubits=random.randint(2, 10),
                    num_gates=random.randint(5, 50),
                    circuit_depth=random.randint(3, 30),
                    optimization_level=random.choice([0, 1, 2, 3])
                )
                db.add(stats)
            conv_count += 1
        print(f"   ✅ Created {conv_count} conversions")
                
        # ────────────────────────────
        # 6. SIMULATIONS
        # ────────────────────────────
        print("🔬 Creating Simulations...")
        sim_count = 0
        for i in range(10):
            user = random.choice(users)
            status = random.choice(list(ExecutionStatus))
            simulation = Simulation(
                user_id=user.id,
                qasm_code=SAMPLE_QASM,
                backend=random.choice(list(SimulationBackend)),
                shots=random.choice([128, 512, 1024, 2048, 4096]),
                status=status,
                results_json={"00": 512, "11": 512} if status == ExecutionStatus.SUCCESS else None,
                execution_time_ms=random.randint(100, 2000) if status == ExecutionStatus.SUCCESS else None,
                error_message="Simulation error" if status == ExecutionStatus.FAILED else None
            )
            db.add(simulation)
            sim_count += 1
        print(f"   ✅ Created {sim_count} simulations")
            
        # ────────────────────────────
        # 7. SESSIONS
        # ────────────────────────────
        print("🔑 Creating Sessions...")
        sess_count = 0
        for i in range(5):
            user = random.choice(users)
            session = Session(
                user_id=user.id,
                session_token=str(uuid.uuid4()),
                session_type=random.choice(list(SessionType)),
                ip_address=f"192.168.1.{random.randint(1, 255)}",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                expires_at=datetime.utcnow() + timedelta(days=1)
            )
            db.add(session)
            sess_count += 1
        print(f"   ✅ Created {sess_count} sessions")
            
        # ────────────────────────────
        # 8. API ACTIVITY
        # ────────────────────────────
        print("📊 Creating API Activities...")
        endpoints = ["/api/auth/login", "/api/files", "/api/shared/", "/api/converter/convert", "/api/simulator/simulate", "/api/projects"]
        methods = ["GET", "POST", "PUT", "DELETE"]
        activity_count = 0
        for i in range(20):
            user = random.choice(users)
            activity = ApiActivity(
                user_id=user.id,
                endpoint=random.choice(endpoints),
                method=random.choice(methods),
                status_code=random.choice([200, 201, 400, 401, 404, 500]),
                ip_address=f"10.0.0.{random.randint(1, 255)}",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                response_time_ms=random.randint(5, 500),
                created_at=datetime.utcnow() - timedelta(hours=random.randint(1, 168))
            )
            db.add(activity)
            activity_count += 1
        print(f"   ✅ Created {activity_count} API activities")

        # ────────────────────────────
        # 9. SHARED SNIPPETS
        # ────────────────────────────
        print("🌐 Creating Shared Snippets...")
        snippet_titles = [
            "Bell State Demo", "Grover 2-Qubit Search", "QRNG Generator",
            "Deutsch-Jozsa Algorithm", "VQC Classifier", "Quantum Teleportation"
        ]
        snippet_count = 0
        for i, title in enumerate(snippet_titles):
            author = users[i % len(users)]
            fw = FRAMEWORKS[i % len(FRAMEWORKS)]
            snippet = SharedSnippet(
                id=f"share-{title.lower().replace(' ', '-')}-{i+1}",
                author_id=author.id,
                author_name=author.full_name,
                title=title,
                description=f"A community shared example demonstrating {title.lower()}.",
                framework=fw,
                difficulty=random.choice(DIFFICULTIES),
                category=random.choice(CATEGORIES),
                tags=SHARED_TAGS[i % len(SHARED_TAGS)],
                code=SAMPLE_CODES[fw],
                filename=f"{title.lower().replace(' ', '_')}.py",
                created_at=datetime.utcnow() - timedelta(days=random.randint(1, 14))
            )
            db.add(snippet)
            snippet_count += 1
        print(f"   ✅ Created {snippet_count} shared snippets")

        # ────────────────────────────
        # 10. ACHIEVEMENTS
        # ────────────────────────────
        print("🏆 Creating Achievements...")
        achievement_objs = []
        for ach_data in ACHIEVEMENTS:
            achievement = Achievement(
                name=ach_data["name"],
                description=ach_data["description"],
                category=ach_data["category"],
                criteria=ach_data["criteria"],
                reward_xp=ach_data["reward_xp"],
                rarity=ach_data["rarity"],
                icon_name=ach_data["icon_name"],
                is_hidden=False
            )
            db.add(achievement)
            achievement_objs.append(achievement)
        
        db.flush()
        for a in achievement_objs:
            db.refresh(a)
        print(f"   ✅ Created {len(achievement_objs)} achievements")
        
        # ────────────────────────────
        # 11. USER GAMIFICATION
        # ────────────────────────────
        print("🎮 Creating User Gamification stats...")
        gam_count = 0
        for user in users:
            xp = random.randint(0, 5000)
            level = max(1, xp // 500)
            gamification = UserGamification(
                user_id=user.id,
                total_xp=xp,
                level=level,
                current_streak=random.randint(0, 14),
                longest_streak=random.randint(3, 30),
                last_activity_date=date.today() - timedelta(days=random.randint(0, 3))
            )
            db.add(gamification)
            gam_count += 1
        print(f"   ✅ Created {gam_count} gamification profiles")

        # ────────────────────────────
        # 12. GAMIFICATION ACTIVITIES
        # ────────────────────────────
        print("📈 Creating Gamification Activities...")
        activity_types = ["simulation", "conversion", "file_save", "shared_snippet", "login"]
        gam_act_count = 0
        for i in range(15):
            user = random.choice(users)
            act_type = random.choice(activity_types)
            gam_activity = GamificationActivity(
                user_id=user.id,
                activity_type=act_type,
                xp_awarded=random.choice([10, 25, 50, 100]),
                activity_metadata={"detail": f"Auto-generated {act_type} activity"},
                created_at=datetime.utcnow() - timedelta(hours=random.randint(1, 168))
            )
            db.add(gam_activity)
            gam_act_count += 1
        print(f"   ✅ Created {gam_act_count} gamification activities")

        # ────────────────────────────
        # 13. USER ACHIEVEMENTS
        # ────────────────────────────
        print("🥇 Creating User Achievements...")
        ua_count = 0
        for user in users:
            # Give each user 1-3 random achievements
            num_achievements = random.randint(1, min(3, len(achievement_objs)))
            chosen = random.sample(achievement_objs, num_achievements)
            for ach in chosen:
                ua = UserAchievement(
                    user_id=user.id,
                    achievement_id=ach.id,
                    progress={"current": ach.criteria.get("target", 1), "target": ach.criteria.get("target", 1)},
                    unlocked_at=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                )
                db.add(ua)
                ua_count += 1
        print(f"   ✅ Created {ua_count} user achievements")

        # ────────────────────────────
        # COMMIT ALL
        # ────────────────────────────
        db.commit()
        print("\n🎉 Database successfully populated with dummy data!")
        print("   Credentials: any user email with password 'password123'")
        print("   Admin: admin@qcanvas.com / password123")
        
    except Exception as e:
        print(f"\n❌ Error populating database: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    populate_dummy_data()
