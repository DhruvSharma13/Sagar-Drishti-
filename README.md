# 🌊 Sagar Drishti

**Ocean 3D Visualization Platform**

Sagar Drishti ("Ocean Vision") is a web platform for exploring ocean data in an interactive 3D environment. It pairs a 3D frontend with a backend that serves and processes ocean data, so users can see and understand marine conditions visually instead of reading raw numbers.

## ✨ Features

- Interactive 3D ocean visualization
- Backend API for serving ocean data
- Separate frontend and backend for easy development and deployment
- Environment-based configuration via `.env`

## 🛠️ Tech Stack


| Layer    | Technology                                   |
| -------- | -------------------------------------------- |
| Frontend | e.g. React, Three.js / React Three Fiber, Vite |
| Backend  | e.g. Node.js + Express / Python + FastAPI    |
| Data     | e.g. NOAA / INCOIS / Copernicus datasets     |

---

## 📁 Project Structure

```
Sagar-Drishti-/
├── backend/         # API server and data processing
├── frontend/        # 3D visualization web app
├── .env.example     # Template for environment variables
├── .gitignore
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- [Node.js](https://nodejs.org/) 18+ and npm (or Python 3.10+ if your backend uses Python)
- Git

### 1. Clone the repository

```bash
git clone https://github.com/DhruvSharma13/Sagar-Drishti-.git
cd Sagar-Drishti-
```

### 2. Configure environment variables

Copy the example file and fill in your own values:

```bash
cp .env.example .env
```

> Never commit your real `.env` file or API keys.

### 3. Run the backend

```bash
cd backend
npm install
npm start
```

<!-- Python backend? Use instead:
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python main.py
-->

### 4. Run the frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Then open the URL shown in the terminal (usually `http://localhost:5173`).

---

## ⚙️ Environment Variables

See [`.env.example`](.env.example) for the full list. Common ones:

| Variable      | Description                          |
| ------------- | ------------------------------------ |
| `PORT`        | Port for the backend server          |
| `API_KEY`     | Key for your external data provider  |

<!-- TODO: match this table to your .env.example -->

---

## 🗺️ Roadmap

- [ ] Add more ocean data layers
- [ ] Time-based playback of historical data
- [ ] Mobile-friendly controls
- [ ] Deploy a live demo

---

## 🤝 Contributing

Contributions are welcome.

1. Fork the repo
2. Create a branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push: `git push origin feature/your-feature`
5. Open a Pull Request


## 👤 Author

**Dhruv Sharma**
GitHub: [@DhruvSharma13](https://github.com/DhruvSharma13)
