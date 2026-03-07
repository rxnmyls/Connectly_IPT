# Connectly API

A Django REST API for a simple social feed with Google OAuth login and JWT authentication.

---

## ✅ Quick Start (Setup)

### 1) Clone and activate your virtual environment

```bash
cd connectly_project
python -m venv env
# Windows PowerShell
.\env\Scripts\Activate.ps1
```

> 📌 If the repo already contains `env/`, just activate it.

---

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

> 📌 **Image placeholder:** Add a screenshot of installing dependencies (terminal output).

---

### 3) Run migrations

```bash
python manage.py migrate
```

> 📌 **Image placeholder:** Add a screenshot of successful migration output.

---

### 4) Create a superuser

```bash
python manage.py createsuperuser
```

---

## 🔧 Configure Google OAuth (Required for `/auth/google/login/`)

### Option A (recommended): Use Django Admin

1. Run the server:

```bash
python manage.py runserver
```

2. Go to: `http://127.0.0.1:8000/admin/`
3. Log in with the superuser.
4. Under **Social applications**, add a new entry:
   - Provider: **Google**
   - Name: (anything, e.g. `Connectly Google`)
   - Client id: **your Google OAuth client ID**
   - Secret key: **your Google OAuth client secret**
   - Sites: select the site entry (usually `example.com` or `localhost`)

> 📌 **Image placeholder:** Screenshot of the “Social applications” admin form with fields filled.


### Option B: Environment variables (auto-create)

Set these before running the server:

```powershell
$env:GOOGLE_CLIENT_ID="<your-client-id>"
$env:GOOGLE_CLIENT_SECRET="<your-client-secret>"
```

---

## ▶️ Running the Server

```bash
python manage.py runserver
```

Visit:
- API root (if available)
- Admin: `http://127.0.0.1:8000/admin/`

> 📌 **Image placeholder:** Screenshot of the running server / admin dashboard.

---

## 🧪 Testing the API

### 1) Get a JWT (Standard username/password)

**Request:**

```bash
curl -X POST http://127.0.0.1:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"<your-username>","password":"<your-password>"}'
```

**Expected response:**

```json
{
  "access": "<jwt-access-token>",
  "refresh": "<jwt-refresh-token>"
}
```

---

### 2) Get a JWT via Google OAuth

1. Obtain a Google access token (e.g., from Google OAuth Playground).
2. Call the API:

```bash
curl -X POST http://127.0.0.1:8000/auth/google/login/ \
  -H "Content-Type: application/json" \
  -d '{"access_token": "<google-access-token>"}'
```

**Expected response:**

```json
{
  "access": "<jwt-access-token>",
  "refresh": "<jwt-refresh-token>"
}
```

> 📌 **Image placeholder:** Screenshot of Postman request/response for Google login.

---

## 📰 News Feed Endpoint (GET /feed/)

### ✅ Basic paginated request

```bash
curl "http://127.0.0.1:8000/feed/?page=1&page_size=5"
```

### ✅ Example response

```json
{
  "page": 1,
  "page_size": 5,
  "total": 12,
  "results": [
    {"id": 12, "content": "...", "created_at": "2026-03-07T.."},
    ...
  ]
}
```

> 📌 **Image placeholder:** Screenshot of a successful feed response.

### ✅ Filtering by user

```bash
curl "http://127.0.0.1:8000/feed/?user=alice&page=1&page_size=5"
```

### ✅ Error handling (invalid params)

```bash
curl "http://127.0.0.1:8000/feed/?page=abc&page_size=5"
```

**Response:**

```json
{
  "detail": "Invalid page parameter. Must be an integer >= 1."
}
```

> 📌 **Image placeholder:** Screenshot of invalid parameter error response.

---

## 🔐 Using the JWT for protected actions

### Create a post (requires JWT)

```bash
curl -X POST http://127.0.0.1:8000/api/posts/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt-access-token>" \
  -d '{"content":"Hello from Postman"}'
```

---

## ✅ Notes / Tips

- If your JWT expires, refresh it:

```bash
curl -X POST http://127.0.0.1:8000/api/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh":"<jwt-refresh-token>"}'
```

- Use the admin UI to manage users, posts, and the Google SocialApp configuration.

---

### 🖼️ Images

When adding images to this README, include them where indicated by **Image placeholder**. Example:

```markdown
![Dependency install output](images/install.png)
```

Place screenshots (e.g. Postman request/response, admin screens, server output) in an `images/` folder and reference them in the appropriate sections.
