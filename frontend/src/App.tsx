import { Navigate, Route, Routes } from 'react-router-dom';
import { HomePage } from './pages/HomePage';
import { GeneMatchPage } from './pages/GeneMatchPage';
import { GeneExpressionsPage } from './pages/GeneExpressionsPage';
import { ExcelViewerPage } from './pages/ExcelViewerPage';
import { PpiInteractionPage } from './pages/PpiInteractionPage';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/geneMatch" element={<GeneMatchPage />} />
      <Route path="/geneExpressions" element={<GeneExpressionsPage />} />
      <Route path="/excelViewer" element={<ExcelViewerPage />} />
      <Route path="/ppiInteraction" element={<PpiInteractionPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}


