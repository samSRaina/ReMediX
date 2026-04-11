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
1. Start backend (`uvicorn`) on `http://127.0.0.1:8000`.
2. In this folder install deps and run Vite:

```powershell
Set-Location "D:\PycharmProjects\drugRepurpose-app\frontend"
npm install
npm run dev
```

Vite proxies `/api`, `/data`, and `/static` requests to the FastAPI server.

## Build
```powershell
Set-Location "D:\PycharmProjects\drugRepurpose-app\frontend"
npm run build
```

The build output is created in `frontend/dist`.

## Notes
- If your backend runs on a different host/port, set `VITE_API_BASE_URL`.
- API typings are defined in `src/types/api.ts` and fetch wrappers in `src/lib/api.ts`.
- This frontend is intended to replace the old Jinja/vanilla-JS page UX.

