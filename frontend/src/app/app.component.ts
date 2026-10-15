import { Component } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink],
  template: `
    <nav class="navbar navbar-expand-lg px-3 px-md-4 py-3" style="background:#f7f3e9;border-bottom:1px solid var(--line)">
      <div class="container-xl">
        <a class="navbar-brand nav-brand" routerLink="/">Eco Infra Studio</a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#nav">
          <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="nav">
          <div class="navbar-nav ms-auto gap-lg-3">
            <a class="nav-link" routerLink="/">Overview</a>
            <a class="nav-link" routerLink="/design">Design a site</a>
          </div>
        </div>
      </div>
    </nav>
    <router-outlet />
    <footer class="py-4 mt-5" style="border-top:1px solid var(--line);color:#5c6656">
      <div class="container-xl small d-flex flex-wrap justify-content-between gap-2">
        <span>Sustainable infrastructure design · environmental data · code checks · Blender 3D</span>
        <span>Models export as .blend, .glb, and 3D-printable .stl</span>
      </div>
    </footer>
  `,
})
export class AppComponent {}
