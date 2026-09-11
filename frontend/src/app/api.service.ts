import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface SummarizeResponse {
  summary: string;
  raw_summary?: string;
  filtered_summary?: string;
  url: string;
  model?: string;
  duration?: number;
}

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  // Dynamically use the current host's IP/hostname
  private apiUrl = `http://${window.location.hostname}:8000/api`;

  constructor(private http: HttpClient) { }

  summarize(
    url: string, 
    limit: number = 500, 
    stripHidden: boolean = true, 
    stripUnicode: boolean = true, 
    usePytector: boolean = true,
    stripQuery: boolean = true,
    forceOllama: boolean = false,
    useHumanizer: boolean = true
  ): Observable<SummarizeResponse> {
    return this.http.post<SummarizeResponse>(`${this.apiUrl}/summarize`, { 
      url, 
      limit,
      strip_hidden: stripHidden,
      strip_unicode: stripUnicode,
      use_pytector: usePytector,
      strip_query: stripQuery,
      force_ollama: forceOllama,
      use_humanizer: useHumanizer
    });
  }

  postToMastodon(summary: string, url: string): Observable<{ success: boolean }> {
    return this.http.post<{ success: boolean }>(`${this.apiUrl}/mastodon`, { summary, url });
  }
}
