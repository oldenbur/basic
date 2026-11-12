import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import "./styles.css";
import { Browse } from "./pages/Browse";
import { Issues } from "./pages/Issues";
import { Status } from "./pages/Status";

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1 } } });

function App() {
  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">PhotoIndex</span>
        <nav>
          <NavLink to="/" end>Library</NavLink>
          <NavLink to="/issues">Naming issues</NavLink>
          <NavLink to="/status">Pipeline</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Browse />} />
          <Route path="/folders/:id" element={<Browse />} />
          <Route path="/issues" element={<Issues />} />
          <Route path="/status" element={<Status />} />
        </Routes>
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
