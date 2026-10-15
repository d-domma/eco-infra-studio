import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { DesignRequest, DesignResult } from './models';

@Injectable({ providedIn: 'root' })
export class DesignService {
  constructor(private http: HttpClient) {}

  create(req: DesignRequest) {
    return this.http.post<DesignResult>('/api/designs', req);
  }

  get(id: string) {
    return this.http.get<DesignResult>(`/api/designs/${id}`);
  }

  fileUrl(id: string, name: string) {
    return `/api/designs/${id}/files/${name}`;
  }
}
