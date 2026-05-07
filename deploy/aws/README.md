# Deploy to AWS (ECS Fargate + RDS)

## Architecture

```
Internet → ALB → ECS Fargate (rag-backend / rag-frontend / rag-admin-ui)
                                      ↓
                              RDS Postgres 16 (pgvector)
```

Secrets are stored in SSM Parameter Store (SecureString) and injected into containers at runtime — no secrets in environment variables or images.

## Prerequisites

- AWS CLI configured (`aws configure`)
- Docker installed
- ECR repos created (one per service)

## Steps

### 1. Create ECR repositories

```bash
REGION=us-east-1
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

for repo in rag-backend rag-frontend rag-admin-ui; do
  aws ecr create-repository --repository-name $repo --region $REGION
done
```

### 2. Build and push images

```bash
# Login to ECR
aws ecr get-login-password --region $REGION | \
  docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.$REGION.amazonaws.com

# Build and push each service
for svc in backend frontend admin-ui; do
  IMAGE=$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/rag-$svc:latest
  docker build -t $IMAGE ./$svc
  docker push $IMAGE
done
```

### 3. Deploy the CloudFormation stack

```bash
aws cloudformation deploy \
  --stack-name rag-platform \
  --template-file deploy/aws/cloudformation.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    VpcId=vpc-XXXXXXXX \
    SubnetIds=subnet-AAAA,subnet-BBBB \
    ECRAccountId=$ACCOUNT \
    ECRRegion=$REGION \
    DBPassword=<strong-password> \
    GoogleApiKey=<your-key> \
    JwtSecret=$(openssl rand -hex 32) \
    AdminSecretKey=$(openssl rand -hex 24)
```

### 4. Enable pgvector in RDS

```bash
# Get the RDS endpoint from stack outputs
ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name rag-platform \
  --query "Stacks[0].Outputs[?OutputKey=='RDSEndpoint'].OutputValue" \
  --output text)

# Connect and enable the extension
psql "postgresql://rag:<DBPassword>@$ENDPOINT:5432/rag_db" \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 5. Run migrations

```bash
DB_URL="postgresql://rag:<DBPassword>@$ENDPOINT:5432/rag_db"
for f in $(ls backend/src/rag_chatbot/db/migrations/*.sql | sort); do
  echo "Applying $f..."
  psql "$DB_URL" -f "$f"
done
```

### 6. Register ECS task definitions and create services

```bash
# Substitute placeholders in task definitions
sed -i "s/ACCOUNT_ID/$ACCOUNT/g; s/REGION/$REGION/g" deploy/aws/ecs-task-*.json

# Register
for f in deploy/aws/ecs-task-*.json; do
  aws ecs register-task-definition --cli-input-json file://$f
done

# Create services (repeat for frontend and admin-ui, adjusting port/TG)
CLUSTER=rag-platform
aws ecs create-service \
  --cluster $CLUSTER \
  --service-name rag-backend \
  --task-definition rag-backend \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-AAAA,subnet-BBBB],securityGroups=[sg-XXXX],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=<TargetGroupBackend ARN>,containerName=rag-backend,containerPort=8000"
```

## Estimated cost (us-east-1, minimal sizing)

| Resource | Spec | $/month |
|----------|------|---------|
| ECS Fargate — backend | 0.5 vCPU / 1 GB | ~$15 |
| ECS Fargate — frontend | 0.25 vCPU / 0.5 GB | ~$7 |
| ECS Fargate — admin-ui | 0.25 vCPU / 0.5 GB | ~$7 |
| RDS Postgres | db.t4g.micro / 20 GB gp3 | ~$15 |
| ALB | 1 LCU est. | ~$18 |
| **Total** | | **~$62/mo** |

## CI/CD (GitHub Actions)

Add `.github/workflows/deploy-aws.yml`:

```yaml
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - name: Build and push images
        run: |
          ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
          aws ecr get-login-password | docker login --username AWS --password-stdin \
            $ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
          for svc in backend frontend admin-ui; do
            IMAGE=$ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/rag-$svc:${{ github.sha }}
            docker build -t $IMAGE ./$svc && docker push $IMAGE
          done
      - name: Update ECS services
        run: |
          for svc in rag-backend rag-frontend rag-admin-ui; do
            aws ecs update-service --cluster rag-platform --service $svc --force-new-deployment
          done
```
