# React UI (Modernized Frontend)

This folder contains a modern React + TypeScript + Tailwind UI for the existing FastAPI backend.

## Stack
- React 18 + TypeScript
- Tailwind CSS (utility-first)
- Headless UI (`@headlessui/react`) for accessible tabs + autocomplete
- Fetch API with typed response models

## Features implemented
- Full routed frontend with unified modern UI/UX on all pages:
  - `/` Home + compound profile + bioactivity tabs
  - `/geneMatch` disease selection + matching + score + signature table
  - `/geneExpressions` searchable paginated gene expression explorer
  - `/excelViewer` sheet tabs + paginated table viewer
  - `/ppiInteraction` image gallery + preview modal + quick file links
- Typed fetch clients for all corresponding FastAPI endpoints
- Shared layout/navigation and consistent card/button/table visual language
- Loading, empty, and error states across pages
- Copy-to-clipboard and sortable/filterable bioactivity table on home page

## Run in development
Before starting, create your local env file:

```powershell
Set-Location "D:\PycharmProjects\drugRepurpose-app\frontend"
Copy-Item ".env.example" ".env.local"
```

1. Install frontend dependencies once:

```powershell
Set-Location "D:\PycharmProjects\drugRepurpose-app\frontend"
npm install
```

2. Start both backend and frontend from the project root with the single entrypoint:

```powershell
Set-Location "D:\PycharmProjects\drugRepurpose-app"
uv run python run.py
```

Vite proxies `/api` and `/data` requests to the FastAPI server.

## Build
```powershell
Set-Location "D:\PycharmProjects\drugRepurpose-app\frontend"
npm run build
```

The build output is created in `frontend/dist`.

## Notes
- If your backend runs on a different host/port, set `VITE_API_BASE_URL`.
- API typings are defined in `src/types/api.ts` and fetch wrappers in `src/lib/api.ts`.
- This frontend replaces the old Jinja/vanilla-JS page UX; legacy assets are archived in the repository.
- Gene Expressions sheets load from `src/data/PPInteraction/xlsxData`, and optional image assets (png/jpg/etc.) load from `src/data/PPInteraction`.

## run in production
```powershell
fastapi run
```

## Deploy on Netlify

This repository includes a root `netlify.toml` with:

- base directory: `frontend`
- build command: `npm run build`
- publish directory: `dist`
- SPA fallback redirect to `index.html`

Set this environment variable in Netlify:

- `VITE_API_BASE_URL=https://<your-render-backend>`

Use this template file while configuring Netlify:

- `frontend/.env.netlify.example`

Example:

- `VITE_API_BASE_URL=https://drugrepurpose-api.onrender.com`
