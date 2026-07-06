# FastAPI Middleware Service

A production-ready FastAPI application featuring three custom middleware layers:
1. **Request Context Middleware**: Tracking and propagation of request IDs.
2. **Scoped CORS Middleware**: Dynamic origin validation restricting access only to the assigned domain and IITM exam domains.
3. **Per-client Rate Limiter**: Independent token-bucket rate limiting (9 requests per 10 seconds) per `X-Client-Id`.

The project is packaged with Docker and ready for immediate deployment on Render.

---

## Assigned Configuration Values

- **Email**: `23f1002228@ds.study.iitm.ac.in`
- **Allowed CORS Origin**: `https://app-g8swuy.example.com` (and IITM domains)
- **Rate Limit**: 9 requests
- **Window**: 10 seconds
- **Endpoint**: `GET /ping`

---

## Project Structure

```
middleware-api/
├── main.py            # FastAPI Application and custom ASGI Middlewares
├── requirements.txt   # Python Dependencies (fastapi, uvicorn)
├── Dockerfile         # Docker container configuration
├── start.sh           # Shell entrypoint for starting uvicorn
├── verify.py          # Automated verification script
├── README.md          # Project instructions (this file)
└── .gitignore         # Git ignore patterns
```

---

## Local Setup

### 1. Create a Virtual Environment and Install Dependencies
Ensure you have Python 3.11+ installed. Run the following commands:

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows (Command Prompt):
venv\Scripts\activate
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Start the Server Locally
Run the start script or run Uvicorn directly:

```bash
# Using start.sh (bash environments)
./start.sh

# Or directly using Uvicorn
uvicorn main:app --host 127.0.0.1 --port 10000
```

The API will be accessible at `http://127.0.0.1:10000`.

---

## Docker Setup

### 1. Build the Docker Image
```bash
docker build -t middleware-api .
```

### 2. Run the Container
```bash
docker run -d -p 10000:10000 --name middleware-service middleware-api
```

---

## Verification & Testing Instructions

We have provided a verification script `verify.py` which automatically runs all grading test cases (both local and CORS preflight tests).

### 1. Run local tests (starts uvicorn automatically)
Make sure port `10000` is free, then run:
```bash
python verify.py
```

### 2. Run tests against a running Docker container
If you have the server running in Docker (or locally already on port 10000), run:
```bash
python verify.py --no-start
```

---

## GitHub Push & Render Deployment

### 1. Initialize Git and Push to GitHub
Create a new repository on GitHub and run the following in your project folder:

```bash
git init
git add .
git commit -m "Initial commit of FastAPI middleware service"
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```

### 2. Deploy on Render
1. Go to [Render Dashboard](https://dashboard.render.com/) and click **New > Web Service**.
2. Connect your GitHub repository.
3. In the Web Service configuration settings:
   - **Name**: `middleware-api-service`
   - **Environment / Runtime**: `Docker`
   - **Branch**: `main`
   - **Docker Command**: (Leave empty; Render will automatically execute the `CMD` from our `Dockerfile` which runs `start.sh`)
4. Click **Deploy Web Service**.
5. Render will build the Docker container and expose it on the internet.
