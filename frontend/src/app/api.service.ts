import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

interface SummarizeResponse {
  summary: string;
  url: string;
  model?: string;
}

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private apiUrl = 'http://localhost:8000/api';

  constructor(private http: HttpClient) { }

  summarize(
    url: string, 
    limit: number = 500, 
    stripHidden: boolean = true, 
    stripUnicode: boolean = true, 
    usePytector: boolean = true
  ): Observable<SummarizeResponse> {
    return this.http.post<SummarizeResponse>(`${this.apiUrl}/summarize`, { 
      url, 
      limit,
      strip_hidden: stripHidden,
      strip_unicode: stripUnicode,
      use_pytector: usePytector
    });
  }

  postToMastodon(summary: string, url: string): Observable<{ success: boolean }> {
    return this.http.post<{ success: boolean }>(`${this.apiUrl}/mastodon`, { summary, url });
  }
}
