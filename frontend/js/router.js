import { icon } from "./components/ui.js";
import { state } from "./state.js";

const titles = {
  home: "Fieldnote — Crop health, clearly",
  scan: "Scan a leaf — Fieldnote",
  analyzing: "Checking your leaf — Fieldnote",
  results: "Your scan result — Fieldnote",
  "my-scans": "My scans - Fieldnote",
  history: "My scans — Fieldnote",
  "plant-guide": "Plant guide - Fieldnote",
  library: "Plant guide — Fieldnote",
  "outbreak-map": "Outbreak map - Fieldnote",
  map: "Outbreak Map — Fieldnote",
  treatment: "Treatment Planner — Fieldnote",
  safety: "Safety - Fieldnote",
  limitations: "Limitations & Responsible Use — Fieldnote",
  "admin-feedback": "Feedback Review — Fieldnote Admin",
  "admin-analytics": "Analytics Dashboard — Fieldnote Admin",
  settings: "Settings — Fieldnote",
  styleguide: "Styleguide — Fieldnote",
};

/** Hash-based router for the static single-page app. */
export class HashRouter {
  constructor(root) {
    this.root = root;
    this.cleanup = null;
    this.moduleAttempts = new Map();
    this.routeModules = {
      home: "./pages/home.js",
      scan: "./pages/scanner.js",
      analyzing: "./pages/analysis.js",
      results: "./pages/results.js",
      history: "./pages/history.js",
      library: "./pages/library.js",
      map: "./pages/outbreak-map.js",
      treatment: "./pages/treatment.js",
      limitations: "./pages/limitations.js",
      "admin/feedback": "./pages/admin-feedback.js",
      "admin/analytics": "./pages/admin-analytics.js",
      settings: "./pages/settings.js",
      styleguide: "./pages/styleguide.js",
    };
    this.routes = {
      home: async () => {
        const page = await this.loadPage("home");
        if (!page) return;
        this.render(page.homePage());
        this.mountLeafExplode();
      },
      scan: async () => {
        const page = await this.loadPage("scan");
        if (page) this.cleanup = page.scannerPage(this.root);
      },
      analyzing: async () => {
        const page = await this.loadPage("analyzing");
        if (page) this.render(page.analysisPage());
      },
      results: async () => {
        const page = await this.loadPage("results");
        if (page) await page.resultsPage(this.root);
      },
      history: async () => {
        const page = await this.loadPage("history");
        if (page) await page.historyPage(this.root);
      },
      library: async () => {
        const page = await this.loadPage("library");
        if (page) page.libraryPage(this.root);
      },
      map: async () => {
        const page = await this.loadPage("map");
        if (page) await page.outbreakMapPage(this.root);
      },
      treatment: async () => {
        const page = await this.loadPage("treatment");
        if (page) page.treatmentPage(this.root);
      },
      limitations: async () => {
        const page = await this.loadPage("limitations");
        if (page) page.limitationsPage(this.root);
      },
      "admin/feedback": async () => {
        const page = await this.loadPage("admin/feedback");
        if (page) await page.adminFeedbackPage(this.root);
      },
      "admin/analytics": async () => {
        const page = await this.loadPage("admin/analytics");
        if (page) await page.adminAnalyticsPage(this.root);
      },
      settings: async () => {
        const page = await this.loadPage("settings");
        if (page) page.settingsPage(this.root);
      },
      styleguide: async () => {
        const page = await this.loadPage("styleguide");
        if (page) this.render(page.styleguidePage());
      },
    };
    this.aliases = {
      map: "outbreak-map",
      outbreak: "outbreak-map",
      history: "my-scans",
      library: "plant-guide",
      limitations: "safety",
    };
    this.routes["outbreak-map"] = this.routes.map;
    this.routes["my-scans"] = this.routes.history;
    this.routes["plant-guide"] = this.routes.library;
    this.routes.safety = this.routes.limitations;
    window.addEventListener("hashchange", () => this.navigate());
  }

  render(markup) {
    this.root.innerHTML = markup;
  }

  async loadPage(route) {
    const path = this.routeModules[route];
    const attempt = this.moduleAttempts.get(route) || 0;
    const importPath = attempt === 0 ? path : `${path}?retry=${attempt}`;
    try {
      return await import(importPath);
    } catch (error) {
      console.error(`Failed to load route module: ${path}`, error);
      this.moduleAttempts.set(route, attempt + 1);
      this.renderLoadError(path);
      return null;
    }
  }

  renderLoadError(path) {
    this.root.innerHTML = `
      <section class="page-shell container">
        <div class="empty-state" role="alert">
          <h1>This page could not be loaded.</h1>
          <p>Module unavailable: <code>${path}</code></p>
          <button class="button" type="button" data-route-retry>Retry</button>
        </div>
      </section>`;
    this.root.querySelector("[data-route-retry]").addEventListener("click", () => this.navigate());
  }

  mountLeafExplode() {
    const container = this.root.querySelector("[data-leaf-explode]");
    if (!container) return;
    let instance = null;
    let disposed = false;
    const observer = new IntersectionObserver(
      async (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        observer.disconnect();
        try {
          const { LeafExplode } = await import("./components/leaf-explode.js");
          if (disposed || !container.isConnected) return;
          instance = new LeafExplode({ container });
          instance.init();
        } catch (error) {
          console.error("Failed to load route module: ./components/leaf-explode.js", error);
          if (!disposed) {
            const message = document.createElement("div");
            message.className = "leaf-explode__load-error";
            message.setAttribute("role", "alert");
            message.innerHTML =
              '<p>The leaf animation could not be loaded.</p><button type="button">Retry</button>';
            message.querySelector("button").addEventListener("click", () => {
              message.remove();
              this.mountLeafExplode();
            });
            container.querySelector(".leaf-explode__visual")?.append(message);
          }
        }
      },
      { rootMargin: "180px 0px" },
    );
    observer.observe(container);
    this.cleanup = () => {
      disposed = true;
      observer.disconnect();
      instance?.destroy();
    };
  }

  async navigate() {
    this.cleanup?.();
    this.cleanup = null;
    const raw = window.location.hash.replace(/^#\/?/, "") || "home";
    const [requestedRoute] = raw.split("?");
    const route = this.aliases[requestedRoute] || requestedRoute;
    if (requestedRoute !== route && this.aliases[requestedRoute]) {
      window.history.replaceState(
        null,
        "",
        `#/${route}${raw.includes("?") ? `?${raw.split("?").slice(1).join("?")}` : ""}`,
      );
    }
    const handler = this.routes[route];
    if (handler) {
      try {
        const output = handler();
        if (output instanceof Promise) await output;
      } catch (error) {
        const path = this.routeModules[route] || "route handler";
        console.error(`Failed to render route module: ${path}`, error);
        this.renderLoadError(path);
      }
      document.title = titles[route] || titles.home;
      state.lastRoute = route;
      this.updateNavigation(route);
    } else {
      this.render(
        `<section class="page-shell container"><div class="empty-state"><span class="empty-icon">${icon("leaf")}</span><h1>That field path isn’t here.</h1><p>The page may have moved. Let’s get you back to your crop dashboard.</p><a class="button" href="#/">Back to Fieldnote ${icon("home")}</a></div></section>`,
      );
      document.title = "Page not found — Fieldnote";
      this.updateNavigation("404");
    }
    this.root.focus({ preventScroll: true });
  }

  updateNavigation(route) {
    const active = route === "analyzing" || route === "results" ? "scan" : route;
    document.querySelectorAll("[data-nav]").forEach((link) => {
      const isActive = link.dataset.nav === active || (active === "home" && link.dataset.nav === "home");
      if (isActive) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  }
}
