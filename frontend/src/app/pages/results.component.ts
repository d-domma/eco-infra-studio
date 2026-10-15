import { DecimalPipe } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { DesignService } from '../design.service';
import { DesignResult } from '../models';
import { CameraView, ViewMode, ViewerComponent } from './viewer.component';

@Component({
  selector: 'app-results',
  imports: [RouterLink, DecimalPipe, ViewerComponent],
  template: `
    <div class="container-xl py-4 py-md-5">
      @if (!result) {
        <p>Loading design…</p>
      } @else {
        <div class="d-flex flex-wrap justify-content-between gap-3 mb-4">
          <div>
            <p class="small text-uppercase fw-semibold mb-1" style="color:var(--leaf)">Design {{ result.id }}</p>
            <h1 class="h2 mb-1">{{ result.environment.location.name }}</h1>
            <p class="mb-0" style="color:#4a5446">
              {{ result.environment.climate_zone }}
              @if (result.zoning) {
                · {{ result.zoning.city }}{{ result.zoning.district ? ' ' + result.zoning.district : '' }}
              }
              · {{ result.compliance.zone }}
            </p>
          </div>
          <a routerLink="/design" class="btn btn-outline-secondary rounded-pill align-self-start">New design</a>
        </div>

        <p class="fs-5 mb-4" style="max-width:52rem">{{ result.summary }}</p>

        <div class="row g-4 mb-4">
          <div class="col-lg-7">
            <div class="d-flex flex-wrap gap-2 mb-2">
              @for (v of viewOptions; track v.id) {
                <button
                  class="btn btn-sm rounded-pill"
                  [class.btn-moss]="viewMode === v.id"
                  [class.btn-outline-secondary]="viewMode !== v.id"
                  (click)="viewMode = v.id"
                >
                  {{ v.label }}
                </button>
              }
            </div>
            <div class="card-quiet p-2" style="height:520px">
              <app-viewer
                [spec]="result.proposed"
                [lotWidth]="result.request.lot_width_m"
                [lotDepth]="result.request.lot_depth_m"
                [glbUrl]="glbUrl"
                [viewMode]="viewMode"
                [views]="views"
              />
            </div>
            <p class="small mt-2 mb-2" style="color:#66705f">
              Drag to orbit, scroll to zoom, right-drag to pan. Interior view is from the living room; cutaway hides the street facade so the plan reads like a section model.
            </p>
            <div class="d-flex flex-wrap gap-2 mt-2">
              @if (result.files['model.blend']) {
                <a class="btn btn-moss rounded-pill" [href]="file('model.blend')">Download Blender file</a>
              }
              @if (result.files['model.stl']) {
                <a class="btn btn-outline-secondary rounded-pill" [href]="file('model.stl')">STL for 3D print</a>
              }
              @if (result.files['model.glb']) {
                <a class="btn btn-outline-secondary rounded-pill" [href]="file('model.glb')">GLB preview</a>
              }
              @if (result.files['preview.png']) {
                <a class="btn btn-outline-secondary rounded-pill" [href]="file('preview.png')">Exterior still</a>
              }
              @if (result.files['interior.png']) {
                <a class="btn btn-outline-secondary rounded-pill" [href]="file('interior.png')">Interior still</a>
              }
              @if (result.files['cutaway.png']) {
                <a class="btn btn-outline-secondary rounded-pill" [href]="file('cutaway.png')">Cutaway still</a>
              }
            </div>
            @if (!result.blender_ready) {
              <div class="alert alert-warning mt-3">
                Blender did not finish this model. {{ result.blender_error }}
              </div>
            }
          </div>
          <div class="col-lg-5">
            <div class="card-quiet p-4 mb-3">
              <h2 class="h5">Proposed vs conventional</h2>
              <div class="row g-3 mt-1">
                <div class="col-6 metric">
                  <div class="small text-uppercase">Embodied CO₂e</div>
                  <div class="fs-4">{{ result.proposed_impact.embodied_kg_co2e | number: '1.0-0' }}</div>
                  <div class="small">vs {{ result.conventional_impact.embodied_kg_co2e | number: '1.0-0' }} kg conventional</div>
                </div>
                <div class="col-6 metric">
                  <div class="small text-uppercase">Net annual CO₂e</div>
                  <div class="fs-4">{{ result.proposed_impact.net_annual_kg_co2e | number: '1.0-0' }}</div>
                  <div class="small">vs {{ result.conventional_impact.net_annual_kg_co2e | number: '1.0-0' }} kg</div>
                </div>
                <div class="col-6 metric">
                  <div class="small text-uppercase">Green space</div>
                  <div class="fs-4">{{ result.proposed_impact.green_space_pct }}%</div>
                  <div class="small">vs {{ result.conventional_impact.green_space_pct }}%</div>
                </div>
                <div class="col-6 metric">
                  <div class="small text-uppercase">Stormwater kept</div>
                  <div class="fs-4">{{ result.proposed_impact.stormwater_retained_m3 }} m³</div>
                  <div class="small">on-site retention estimate</div>
                </div>
              </div>
            </div>
            @if (result.zoning || result.cost) {
              <div class="card-quiet p-4 mb-3">
                <h2 class="h5">Area rules & budget</h2>
                @if (result.zoning) {
                  <p class="small mb-2" style="color:#66705f">{{ result.zoning.source }}</p>
                  <div class="row g-2 small mb-2">
                    <div class="col-6">FAR ≤ {{ result.zoning.far }}</div>
                    <div class="col-6">Height ≤ {{ result.zoning.height_m }} m</div>
                    <div class="col-6">Coverage ≤ {{ result.zoning.coverage * 100 | number: '1.0-0' }}%</div>
                    <div class="col-6">Open space ≥ {{ result.zoning.green * 100 | number: '1.0-0' }}%</div>
                    <div class="col-6">Front {{ result.zoning.front_m }} m</div>
                    <div class="col-6">Side {{ result.zoning.side_m }} m / rear {{ result.zoning.rear_m }} m</div>
                  </div>
                }
                @if (result.cost) {
                  <div class="d-flex justify-content-between align-items-baseline">
                    <div>
                      <div class="small text-uppercase">Screening cost</div>
                      <div class="fs-4">{{ '$' }}{{ result.cost.estimate_usd | number: '1.0-0' }}</div>
                    </div>
                    <div class="text-end">
                      <div class="small text-uppercase">{{ result.cost.tier }} cap</div>
                      <div class="fs-5">{{ '$' }}{{ result.cost.cap_usd | number: '1.0-0' }}</div>
                      <strong [class.pass]="result.cost.within_budget" [class.fail]="!result.cost.within_budget">
                        {{ result.cost.within_budget ? 'Within budget' : 'Over cap' }}
                      </strong>
                    </div>
                  </div>
                  <p class="small mt-2 mb-0" style="color:#66705f">{{ result.cost.basis }}</p>
                }
              </div>
            }
            <div class="card-quiet p-4">
              <div class="d-flex justify-content-between">
                <h2 class="h5 mb-0">Code check</h2>
                <strong [class.pass]="result.compliance.passed" [class.fail]="!result.compliance.passed">
                  {{ result.compliance.passed ? 'Required checks passed' : 'Review required' }} · {{ result.compliance.score }}
                </strong>
              </div>
              <p class="small mt-2" style="color:#66705f">{{ result.compliance.jurisdiction }}</p>
              <div class="table-responsive">
                <table class="table table-sm align-middle mb-0">
                  <tbody>
                    @for (c of result.compliance.checks; track c.code) {
                      <tr>
                        <td>
                          <div class="fw-semibold">{{ c.title }}</div>
                          <div class="small" style="color:#66705f">{{ c.guidance }}</div>
                        </td>
                        <td class="text-nowrap small">{{ c.actual }}</td>
                        <td class="text-end" [class.pass]="c.passed" [class.fail]="!c.passed">
                          {{ c.passed ? 'Pass' : 'Fail' }}
                        </td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        @if (result.search) {
          <div class="card-quiet p-4 mb-4">
            <h2 class="h5">AI search under this area's rules</h2>
            <p class="mb-3">{{ result.search.selected_reason }}</p>
            <div class="row g-3">
              <div class="col-md-3 metric">
                <div class="small text-uppercase">Variants tested</div>
                <div class="fs-4">{{ result.search.n_sampled }}</div>
                <div class="small">{{ result.search.n_legal }} legal and in budget</div>
              </div>
              <div class="col-md-3 metric">
                <div class="small text-uppercase">KNN predicted EUI</div>
                <div class="fs-4">{{ result.search.knn_eui_kbtu_ft2 ?? result.search.proposed_eui_kbtu_ft2 }}</div>
                <div class="small">kBtu/ft² from {{ result.search.knn_n || 0 }} LL84 peers</div>
              </div>
              <div class="col-md-3 metric">
                <div class="small text-uppercase">Screening ops EUI</div>
                <div class="fs-4">{{ result.search.proposed_eui_kbtu_ft2 }}</div>
                <div class="small">kBtu/ft² from the kg CO₂e table</div>
              </div>
              <div class="col-md-3 metric">
                <div class="small text-uppercase">Peer median EUI</div>
                <div class="fs-4">{{ result.search.peers.median_eui_kbtu_ft2 ?? '—' }}</div>
                <div class="small">{{ result.search.budget_rejected || 0 }} over budget</div>
              </div>
            </div>
            <p class="small mt-3 mb-2" style="color:#66705f">{{ result.search.ai_method || result.search.peers.source }}</p>
            @if (result.search.runners_up.length) {
              <div class="table-responsive">
                <table class="table table-sm mb-0">
                  <thead>
                    <tr>
                      <th>Other legal options</th>
                      <th>Stories</th>
                      <th>Embodied kg</th>
                      <th>Net annual kg</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (r of result.search.runners_up; track r.material + r.roof_type + r.stories) {
                      <tr>
                        <td>{{ r.material.replace('_', ' ') }} · {{ r.roof_type.replace('_', ' ') }}</td>
                        <td>{{ r.stories }}</td>
                        <td>{{ r.embodied_kg_co2e | number: '1.0-0' }}</td>
                        <td>{{ r.net_annual_kg_co2e | number: '1.0-0' }}</td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
            }
          </div>
        }

        <div class="row g-4">
          <div class="col-md-6">
            <div class="card-quiet p-4 h-100">
              <h2 class="h5">Environmental snapshot</h2>
              <ul class="list-unstyled mb-0">
                <li>Mean temperature: {{ result.environment.mean_temp_c }} °C</li>
                <li>Annual precipitation: {{ result.environment.annual_precip_mm | number: '1.0-0' }} mm</li>
                <li>Solar resource: {{ result.environment.annual_solar_kwh_m2 | number: '1.0-0' }} kWh/m²</li>
                <li>Nearby green space: {{ result.environment.nearby_green_m2 | number: '1.0-0' }} m² ({{ result.environment.nearby_park_count }} parks)</li>
                <li>Tree-cover score: {{ result.environment.tree_cover_score }}</li>
                <li>Sensitivity: {{ result.environment.ecological_sensitivity }}</li>
              </ul>
            </div>
          </div>
          <div class="col-md-6">
            <div class="card-quiet p-4 h-100">
              <h2 class="h5">Recommendations</h2>
              <ul class="mb-0">
                @for (r of result.recommendations; track r) {
                  <li>{{ r }}</li>
                }
              </ul>
            </div>
          </div>
        </div>
      }
    </div>
  `,
})
export class ResultsComponent implements OnInit {
  result?: DesignResult;
  glbUrl: string | null = null;
  viewMode: ViewMode = 'exterior';
  views: Record<string, CameraView> | null = null;
  viewOptions: { id: ViewMode; label: string }[] = [
    { id: 'exterior', label: 'Exterior' },
    { id: 'interior', label: 'Inside' },
    { id: 'cutaway', label: 'Cutaway / plan' },
  ];

  constructor(
    private route: ActivatedRoute,
    private api: DesignService,
    private http: HttpClient,
  ) {}

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id')!;
    this.api.get(id).subscribe((res) => {
      this.result = res;
      this.glbUrl = res.files['model.glb'] ? this.api.fileUrl(res.id, 'model.glb') : null;
      if (res.files['views.json']) {
        this.http.get<Record<string, CameraView>>(this.api.fileUrl(res.id, 'views.json')).subscribe((v) => (this.views = v));
      }
    });
  }

  file(name: string) {
    return this.result ? this.api.fileUrl(this.result.id, name) : '#';
  }
}
