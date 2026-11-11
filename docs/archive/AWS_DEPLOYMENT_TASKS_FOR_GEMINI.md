# AWS Deployment Execution Guide (For Gemini AI)

**To the AI Agent running this**: The user explicitly requested this document to guide you through deploying their Cirq RAG Code Assistant to AWS ECS Fargate. The project infrastructure is ready, Docker slimming is done, and local pgvector DB has been unit tested.

Your goal is to meticulously walk the user through these AWS infrastructure steps! Proceed methodically. Ask the user for their AWS Account ID and primary Region before commencing.

---

### Step 1: ECR Docker Push
1. Extract the current AWS Account ID and Region.
2. Formulate the AWS CLI strings to `aws ecr create-repository --repository-name cirq-agent`.
3. Provide the command to login the Docker CLI: `aws ecr get-login-password | docker login ...`
4. Formulate the `docker build -t cirq-agent:latest -f Cirq-RAG-Code-Assistant/Dockerfile Cirq-RAG-Code-Assistant` command.
5. Ask the user to execute the docker tag and push commands to their new ECR repositoy.

### Step 2: Establish Fargate IAM Roles
1. Provide the JSON definition for the ECS Trust Policy and ask the user to save it.
2. Run `aws iam create-role` to create the `cirq-agent-task-execution-role` and the `cirq-agent-task-role`.
3. Attach `deployment/ecs/execution-role-policy.json` to the Execution Role.
4. Attach `deployment/ecs/task-role-policy.json` to the Task Role.

### Step 3: Populate AWS Secrets Manager [CRITICAL]
Tell the user that they must migrate their **LOCAL** `.env` contents securely into AWS Secrets Manager. Do not let them accidentally upload their `.env` file to the container!
1. Guide them to formulate and run `aws secretsmanager create-secret` for the DB connection string targeting their RDS Postgres.
2. Guide them to do the same for the Cirq API Key `cirq-agent/api-key`.
3. Ask them to transfer the Bedrock ARNs currently stored in their `.env` file to Secrets Manager as:
   - `cirq-agent/bedrock-designer`
   - `cirq-agent/bedrock-optimizer`
   - `cirq-agent/bedrock-validator`
   - `cirq-agent/bedrock-educational`

### Step 4: Postgres Vector Seeding (Cloud Edition)
1. Provide them the one-off command to tunnel the `Cirq-RAG-Code-Assistant/scripts/sql/001_init_pgvector.sql` command onto their remote RDS database to enable vector queries.
2. Export their new RDS DSN (`CIRQ_RAG_DB_URL=...`) in the terminal and execute `python Cirq-RAG-Code-Assistant/scripts/ingest_kb_to_pgvector.py` against the production cloud database. (This will embed standard RAG context into the deployed schema).

### Step 5: ALB and Fargate Launch
1. Guide them to tweak `cirq-agent.taskdef.json` and deploy it using `aws ecs register-task-definition`.
2. Construct the load-balancer configuration assuring it is pointed towards port 8000.
3. Use `aws elbv2 modify-load-balancer-attributes` to strictly raise the ALB idle timeout to `180` seconds (mandated to support Cloud-based LLM token generation latency bounds).
4. Monitor `/health` and verify HTTP 200 OK statuses on the Fargate cluster to declare mission success.
