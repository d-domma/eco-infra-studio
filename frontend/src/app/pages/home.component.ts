import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-home',
  imports: [RouterLink],
  template: `
    <section class="hero py-5">
      <div class="container-xl py-4">
        <div class="row align-items-center g-5">
          <div class="col-lg-7">
            <p class="text-uppercase small fw-semibold mb-2" style="letter-spacing:.14em;color:var(--leaf)">
              Environmental design · code · Blender
            </p>
            <h1 class="display-4 mb-3">Design infrastructure that fits the site, the climate, and the code.</h1>
            <p class="fs-5 mb-4" style="max-width:40rem;color:#3d4a38">
              Enter a place and your preferences. The studio cross-checks open environmental data and model building rules,
              then builds a detailed 3D massing in Blender — ready to edit or 3D print.
            </p>
            <a routerLink="/design" class="btn btn-moss btn-lg px-4 rounded-pill">Start a design</a>
          </div>
          <div class="col-lg-5">
            <div class="card-quiet p-4">
              <h2 class="h4 mb-3">What the pipeline does</h2>
              <ol class="mb-0 ps-3">
                <li class="mb-2">Reads lot size, building type, roof, materials, and sustainability options.</li>
                <li class="mb-2">Pulls climate, air quality, and nearby green space from open APIs.</li>
                <li class="mb-2">Checks setbacks, height, coverage, FAR, open space, and stormwater.</li>
                <li>Generates a Blender scene with landscape, PV, and a printable STL.</li>
              </ol>
            </div>
          </div>
        </div>
      </div>
    </section>
    <section class="container-xl py-4 pb-5">
      <div class="row g-4">
        @for (item of features; track item.title) {
          <div class="col-md-4">
            <div class="card-quiet h-100 p-4">
              <div class="small text-uppercase fw-semibold mb-2" style="color:var(--clay)">{{ item.kicker }}</div>
              <h3 class="h5">{{ item.title }}</h3>
              <p class="mb-0" style="color:#4a5446">{{ item.body }}</p>
            </div>
          </div>
        }
      </div>
    </section>
  `,
})
export class HomeComponent {
  features = [
    {
      kicker: 'Python analysis',
      title: 'Site + climate intelligence',
      body: 'Open-Meteo weather and air quality plus OpenStreetMap parks and habitat within 900 meters of the site.',
    },
    {
      kicker: 'Legal search',
      title: 'Only code-passing variants',
      body: 'Hundreds of envelopes are tested. Required setbacks, height, coverage, FAR, and stormwater are a hard filter — then the lowest-carbon legal option is sent to Blender.',
    },
    {
      kicker: 'NYC stock',
      title: 'Scored against real buildings',
      body: 'PLUTO lots plus LL84 measured energy where it exists. Embodied carbon labels use CLF typical intensities, not a measured LCA for each lot.',
    },
  ];
}
