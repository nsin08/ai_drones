import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import AppShell from './AppShell.jsx';
import LoginPage from './pages/LoginPage.jsx';
import CommandsPage from './pages/CommandsPage.jsx';
import DashboardPage from './pages/DashboardPage.jsx';
import FleetPage from './pages/FleetPage.jsx';
import MissionsPage from './pages/MissionsPage.jsx';
import SettingsPage from './pages/SettingsPage.jsx';
import './v4.css';

export default function V4Routes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/missions" element={<MissionsPage />} />
          <Route path="/fleet" element={<FleetPage />} />
          <Route path="/commands" element={<CommandsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
        <Route path="/login" element={<LoginPage />} />
      </Routes>
    </BrowserRouter>
  );
}
