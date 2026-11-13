import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, NavLink, Outlet, Route, Routes } from "react-router-dom";
import "./styles.css";
import { Browse } from "./pages/Browse";
import { Issues } from "./pages/Issues";
import { Search } from "./pages/Search";
import { Slideshow } from "./pages/Slideshow";
import { Status } from "./pages/Status";
import { Themes } from "./pages/Themes";

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1 } } });

function Layout() {
  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">PhotoIndex</span>
        <nav>
          <NavLink to="/" end>Library</NavLink>
          <NavLink to="/search">Search</NavLink>
          <NavLink to="/themes">Themes</NavLink>
          <NavLink to="/issues">Naming issues</NavLink>
          <NavLink to="/status">Pipeline</NavLink>
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/play" element={<Slideshow />} />
          <Route element={<Layout />}>
            <Route path="/" element={<Browse />} />
            <Route path="/folders/:id" element={<Browse />} />
            <Route path="/search" element={<Search />} />
            <Route path="/themes" element={<Themes />} />
            <Route path="/issues" element={<Issues />} />
            <Route path="/status" element={<Status />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
