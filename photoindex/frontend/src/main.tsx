import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, NavLink, Outlet, Route, Routes } from "react-router-dom";
import "./styles.css";
import { Albums } from "./pages/Albums";
import { Browse } from "./pages/Browse";
import { Compare } from "./pages/Compare";
import { Issues } from "./pages/Issues";
import { People } from "./pages/People";
import { PersonView } from "./pages/Person";
import { Review } from "./pages/Review";
import { Search } from "./pages/Search";
import { Slideshow } from "./pages/Slideshow";
import { Status } from "./pages/Status";
import { Tagging } from "./pages/Tagging";
import { Tags } from "./pages/Tags";
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
          <NavLink to="/people">People</NavLink>
          <NavLink to="/tagging">AI tags</NavLink>
          <NavLink to="/albums">Old albums</NavLink>
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
            <Route path="/people" element={<People />} />
            <Route path="/people/review" element={<Review />} />
            <Route path="/people/:id" element={<PersonView />} />
            <Route path="/tagging" element={<Tagging />} />
            <Route path="/tagging/compare" element={<Compare />} />
            <Route path="/tags" element={<Tags />} />
            <Route path="/albums" element={<Albums />} />
            <Route path="/issues" element={<Issues />} />
            <Route path="/status" element={<Status />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
