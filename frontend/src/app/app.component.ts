import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { ApiService } from './api.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [FormsModule, CommonModule],
  template: `
    <div class="container">
      <header>
        <h1>TL;DR URL Bot</h1>
        <p>Get concise, technical summaries of any webpage.</p>
      </header>

      <main>
        <div class="input-group">
          <input 
            type="text" 
            [(ngModel)]="url" 
            placeholder="Enter URL to summarize (e.g., https://example.com)" 
            [disabled]="loading"
          >
          <button (click)="summarize()" [disabled]="loading || !url">
            {{ loading ? 'Summarizing...' : 'Summarize' }}
          </button>
        </div>

        <div class="options-group">
          <div class="option">
            <label for="limit">Character Limit:</label>
            <input 
              id="limit" 
              type="number" 
              [(ngModel)]="limit" 
              [disabled]="loading"
              min="100" 
              max="2000"
            >
          </div>
        </div>

        <div *ngIf="error" class="error">
          {{ error }}
        </div>

        <div *ngIf="summary" class="result">
          <h3>Summary</h3>
          <p>{{ summary }}</p>
          <div class="meta">
            <small>URL: {{ lastUrl }}</small>
            <button 
              class="mastodon-btn" 
              (click)="postToMastodon()" 
              [disabled]="isPostingToMastodon || mastodonSuccess === true"
            >
              {{ isPostingToMastodon ? 'Posting...' : (mastodonSuccess === true ? 'Posted' : 'Post to Mastodon') }}
            </button>
          </div>
          <div *ngIf="mastodonSuccess !== null" class="mastodon-status-bar" [class.success]="mastodonSuccess" [class.failure]="!mastodonSuccess">
            {{ mastodonSuccess ? '✓ Successfully posted to Mastodon' : '✗ Failed to post to Mastodon' }}
          </div>
        </div>
      </main>

      <footer>
        <p>Powered by Gemini 2.0 Flash</p>
      </footer>
    </div>
  `,
  styles: [`
    .container {
      max-width: 800px;
      margin: 40px auto;
      padding: 20px;
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      color: #333;
    }
    header {
      text-align: center;
      margin-bottom: 40px;
    }
    h1 {
      color: #2c3e50;
      margin-bottom: 10px;
    }
    .input-group {
      display: flex;
      gap: 10px;
      margin-bottom: 20px;
    }
    .options-group {
      display: flex;
      gap: 20px;
      margin-bottom: 30px;
      align-items: center;
      background: #f0f4f8;
      padding: 15px;
      border-radius: 6px;
    }
    .option {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .option label {
      font-weight: 600;
      color: #34495e;
    }
    .option input[type="number"] {
      width: 80px;
      padding: 6px;
      border: 1px solid #ccc;
      border-radius: 4px;
    }
    .checkbox-label {
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .checkbox-label input {
      width: 18px;
      height: 18px;
    }
    input {
      flex: 1;
      padding: 12px;
      font-size: 16px;
      border: 2px solid #ddd;
      border-radius: 6px;
      outline: none;
    }
    input:focus {
      border-color: #3498db;
    }
    button {
      padding: 12px 24px;
      font-size: 16px;
      background-color: #3498db;
      color: white;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      transition: background-color 0.2s;
    }
    button:hover:not(:disabled) {
      background-color: #2980b9;
    }
    button:disabled {
      background-color: #bdc3c7;
      cursor: not-allowed;
    }
    .result {
      margin-top: 30px;
      padding: 20px;
      background-color: #f9f9f9;
      border-left: 5px solid #3498db;
      border-radius: 4px;
    }
    .result h3 {
      margin-top: 0;
      color: #2c3e50;
    }
    .result p {
      line-height: 1.6;
      font-size: 17px;
    }
    .meta {
      margin-top: 15px;
      color: #7f8c8d;
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 10px;
      border-bottom: 1px solid #eee;
      margin-bottom: 10px;
    }
    .mastodon-btn {
      background-color: #6364ff;
      padding: 8px 16px;
      font-size: 14px;
    }
    .mastodon-btn:hover:not(:disabled) {
      background-color: #5657e5;
    }
    .mastodon-status-bar {
      margin-top: 10px;
      font-weight: 600;
      padding: 8px 12px;
      border-radius: 4px;
      font-size: 14px;
    }
    .mastodon-status-bar.success {
      color: #27ae60;
      background-color: #eafaf1;
    }
    .mastodon-status-bar.failure {
      color: #c0392b;
      background-color: #fdecea;
    }
    .error {
      color: #e74c3c;
      padding: 10px;
      background-color: #fadbd8;
      border-radius: 4px;
      margin-bottom: 20px;
    }
    footer {
      margin-top: 50px;
      text-align: center;
      color: #95a5a6;
      font-size: 14px;
    }
  `],
})
export class AppComponent {
  url = '';
  limit = 500;
  
  lastUrl = '';
  summary = '';
  mastodonSuccess: boolean | null = null;
  loading = false;
  isPostingToMastodon = false;
  error = '';

  constructor(private apiService: ApiService) {}

  summarize() {
    if (!this.url) return;

    this.loading = true;
    this.error = '';
    this.summary = '';
    this.mastodonSuccess = null;
    
    this.apiService.summarize(this.url, this.limit).subscribe({
      next: (res) => {
        this.summary = res.summary;
        this.lastUrl = res.url;
        this.loading = false;
      },
      error: (err) => {
        this.error = err.error?.detail || 'An unexpected error occurred. Please try again.';
        this.loading = false;
      }
    });
  }

  postToMastodon() {
    if (!this.summary || !this.lastUrl) return;

    this.isPostingToMastodon = true;
    this.mastodonSuccess = null;

    this.apiService.postToMastodon(this.summary, this.lastUrl).subscribe({
      next: () => {
        this.mastodonSuccess = true;
        this.isPostingToMastodon = false;
      },
      error: (err) => {
        this.mastodonSuccess = false;
        this.isPostingToMastodon = false;
        console.error('Mastodon post failed:', err);
      }
    });
  }
}
