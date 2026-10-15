import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { DesignService } from '../design.service';
import { DesignRequest } from '../models';

@Component({
  selector: 'app-designer',
  imports: [FormsModule],
  template: `
    <div class="container-xl py-4 py-md-5">
      <div class="row g-4">
        <div class="col-lg-4">
          <h1 class="h2 mb-2">Site & preferences</h1>
          <p class="mb-4" style="color:#4a5446">
            Three short steps. We overlay that city's building rules, stay inside your budget, then search legal envelopes with a stock-trained energy model and build the 3D in Blender.
          </p>
          <div class="d-flex flex-column gap-3">
            @for (s of steps; track s.n; let i = $index) {
              <div class="d-flex gap-3 align-items-start">
                <div
                  class="step-dot text-white"
                  [style.background]="step >= i ? 'var(--moss)' : '#c9c3b5'"
                >
                  {{ s.n }}
                </div>
                <div>
                  <div class="fw-semibold">{{ s.title }}</div>
                  <div class="small" style="color:#66705f">{{ s.hint }}</div>
                </div>
              </div>
            }
          </div>
        </div>
        <div class="col-lg-8">
          <div class="card-quiet p-4 p-md-5">
            @if (step === 0) {
              <h2 class="h4 mb-4">Where is the site?</h2>
              <div class="mb-3">
                <label class="form-label">City, address, or region</label>
                <input class="form-control form-control-lg" [(ngModel)]="req.address" name="address" />
              </div>
              <div class="row g-3">
                <div class="col-md-6">
                  <label class="form-label">Lot width (m)</label>
                  <input type="number" class="form-control" [(ngModel)]="req.lot_width_m" name="w" />
                </div>
                <div class="col-md-6">
                  <label class="form-label">Lot depth (m)</label>
                  <input type="number" class="form-control" [(ngModel)]="req.lot_depth_m" name="d" />
                </div>
              </div>
            }
            @if (step === 1) {
              <h2 class="h4 mb-4">Building program</h2>
              <div class="row g-3">
                <div class="col-md-6">
                  <label class="form-label">Building type</label>
                  <select class="form-select" [(ngModel)]="req.building_type" name="type">
                    @for (t of types; track t.id) {
                      <option [value]="t.id">{{ t.label }}</option>
                    }
                  </select>
                </div>
                <div class="col-md-3">
                  <label class="form-label">Stories</label>
                  <input type="number" class="form-control" [(ngModel)]="req.stories" name="stories" min="1" max="12" />
                </div>
                <div class="col-md-3">
                  <label class="form-label">Units</label>
                  <input type="number" class="form-control" [(ngModel)]="req.units" name="units" min="1" />
                </div>
                <div class="col-md-6">
                  <label class="form-label">Roof</label>
                  <select class="form-select" [(ngModel)]="req.roof_type" name="roof">
                    <option value="pitched">Pitched</option>
                    <option value="flat">Flat</option>
                    <option value="green">Green roof</option>
                    <option value="solar_green">Green roof + solar</option>
                  </select>
                </div>
                <div class="col-md-6">
                  <label class="form-label">Primary structure</label>
                  <select class="form-select" [(ngModel)]="req.primary_material" name="mat">
                    <option value="mass_timber">Mass timber</option>
                    <option value="rammed_earth">Rammed earth</option>
                    <option value="brick">Brick</option>
                    <option value="recycled_steel">Recycled steel</option>
                    <option value="concrete">Concrete</option>
                  </select>
                </div>
                <div class="col-md-6">
                  <label class="form-label">Bedrooms (if residential)</label>
                  <input type="number" class="form-control" [(ngModel)]="req.bedrooms" name="bed" />
                </div>
                <div class="col-md-6">
                  <label class="form-label">Parking spaces</label>
                  <input type="number" class="form-control" [(ngModel)]="req.parking_spaces" name="park" />
                </div>
                <div class="col-md-6">
                  <label class="form-label">Construction budget</label>
                  <select class="form-select" [(ngModel)]="req.budget_tier" name="budget">
                    <option value="affordable">Affordable (~$2,600/m² floor cap)</option>
                    <option value="standard">Standard (~$3,400/m² floor cap)</option>
                    <option value="premium">Premium (~$4,600/m² floor cap)</option>
                  </select>
                </div>
              </div>
            }
            @if (step === 2) {
              <h2 class="h4 mb-4">Sustainability priorities</h2>
              <label class="form-label">Green-space priority ({{ req.green_space_priority }} / 5)</label>
              <input type="range" class="form-range mb-4" min="1" max="5" [(ngModel)]="req.green_space_priority" name="gsp" />
              <div class="row g-3">
                <div class="col-md-6">
                  <div class="form-check p-3 rounded-3" style="border:1px solid var(--line)">
                    <input class="form-check-input" type="checkbox" id="solar" [(ngModel)]="req.solar_panels" name="solar" />
                    <label class="form-check-label" for="solar">Rooftop solar array</label>
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="form-check p-3 rounded-3" style="border:1px solid var(--line)">
                    <input class="form-check-input" type="checkbox" id="rain" [(ngModel)]="req.rainwater_harvesting" name="rain" />
                    <label class="form-check-label" for="rain">Rain garden + cistern</label>
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="form-check p-3 rounded-3" style="border:1px solid var(--line)">
                    <input class="form-check-input" type="checkbox" id="native" [(ngModel)]="req.native_landscaping" name="native" />
                    <label class="form-check-label" for="native">Native landscaping</label>
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="form-check p-3 rounded-3" style="border:1px solid var(--line)">
                    <input class="form-check-input" type="checkbox" id="ev" [(ngModel)]="req.ev_charging" name="ev" />
                    <label class="form-check-label" for="ev">EV charging ready</label>
                  </div>
                </div>
              </div>
              @if (error) {
                <div class="alert alert-danger mt-4 mb-0">{{ error }}</div>
              }
            }
            <div class="d-flex justify-content-between mt-4">
              <button class="btn btn-outline-secondary rounded-pill px-4" [disabled]="step === 0 || busy" (click)="step = step - 1">
                Back
              </button>
              @if (step < 2) {
                <button class="btn btn-moss rounded-pill px-4" (click)="step = step + 1">Continue</button>
              } @else {
                <button class="btn btn-clay rounded-pill px-4" [disabled]="busy" (click)="submit()">
                  {{ busy ? 'Building in Blender…' : 'Analyze & generate 3D' }}
                </button>
              }
            </div>
            @if (busy) {
              <p class="small mt-3 mb-0" style="color:#66705f">
                Fetching climate and green-space data, running code checks, then launching Blender. This can take 20–60 seconds.
              </p>
            }
          </div>
        </div>
      </div>
    </div>
  `,
})
export class DesignerComponent {
  step = 0;
  busy = false;
  error = '';
  req: DesignRequest = {
    address: 'Portland, Oregon',
    lot_width_m: 18,
    lot_depth_m: 32,
    building_type: 'single_family',
    stories: 2,
    units: 1,
    bedrooms: 3,
    roof_type: 'green',
    primary_material: 'mass_timber',
    solar_panels: true,
    rainwater_harvesting: true,
    native_landscaping: true,
    ev_charging: true,
    parking_spaces: 1,
    green_space_priority: 4,
    budget_tier: 'standard',
  };
  types = [
    { id: 'single_family', label: 'Single-family house' },
    { id: 'duplex', label: 'Duplex' },
    { id: 'townhouse', label: 'Townhouse' },
    { id: 'apartment', label: 'Apartment building' },
    { id: 'mixed_use', label: 'Mixed-use' },
    { id: 'office', label: 'Office / workspace' },
    { id: 'community', label: 'Community facility' },
  ];
  steps = [
    { n: 1, title: 'Location', hint: 'Address — zoning is looked up for that city' },
    { n: 2, title: 'Program', hint: 'Type, height, materials, and budget cap' },
    { n: 3, title: 'Ecology', hint: 'Energy, water, and landscape' },
  ];

  constructor(
    private api: DesignService,
    private router: Router,
  ) {}

  submit() {
    this.busy = true;
    this.error = '';
    this.api.create(this.req).subscribe({
      next: (res) => this.router.navigate(['/results', res.id]),
      error: (err) => {
        this.busy = false;
        this.error = err?.error?.detail || err.message || 'Generation failed.';
      },
    });
  }
}
