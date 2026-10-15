import { Routes } from '@angular/router';
import { HomeComponent } from './pages/home.component';
import { DesignerComponent } from './pages/designer.component';
import { ResultsComponent } from './pages/results.component';

export const routes: Routes = [
  { path: '', component: HomeComponent },
  { path: 'design', component: DesignerComponent },
  { path: 'results/:id', component: ResultsComponent },
  { path: '**', redirectTo: '' },
];
