import { NavLink } from "react-router-dom";

const navigationItems = [
  {
    label: "Daily",
    path: "/daily",
  },
  {
    label: "Search",
    path: "/search",
  },
  {
    label: "Query",
    path: "/query",
  },
  {
    label: "Documents",
    path: "/documents",
  },
];

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark">P</div>

        <div>
          <div className="brand-name">PAIS</div>
          <div className="brand-subtitle">Intelligence System</div>
        </div>
      </div>

      <nav className="sidebar-nav" aria-label="Primary navigation">
        {navigationItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `nav-item${isActive ? " nav-item-active" : ""}`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <span className="sidebar-footer-label">PAIS V1</span>
      </div>
    </aside>
  );
}

export default Sidebar;