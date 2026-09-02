import { AfterViewInit, Component, ElementRef, ViewChild } from '@angular/core';
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
            #urlInput
            type="text" 
            [(ngModel)]="url" 
            placeholder="Enter URL to summarize (e.g., https://example.com)" 
            [disabled]="loading"
            (keyup.enter)="summarize()"
          >
          <button (click)="summarize()" [disabled]="loading || !url">
            {{ loading ? 'Summarizing...' : 'Summarize' }}
          </button>
          <button 
            *ngIf="summary"
            #mastodonButton
            class="mastodon-btn" 
            (click)="postToMastodon()" 
            [disabled]="isPostingToMastodon || mastodonSuccess === true"
          >
            {{ isPostingToMastodon ? 'Posting...' : (mastodonSuccess === true ? 'Posted' : 'Post to Mastodon') }}
          </button>
          <button 
            *ngIf="summary"
            class="ok-btn"
            (click)="reload()"
          >
            OK
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
          <div class="option">
            <label class="checkbox-label">
              <input type="checkbox" [(ngModel)]="stripHidden" [disabled]="loading"> Strip Hidden HTML
              <a href="https://www.google.com/search?q=Strip+Hidden+HTML" target="_blank" title="Strip Hidden HTML search" style="font-size: 12px; margin-left: 5px;">(?)</a>
            </label>
            <label class="checkbox-label">
              <input type="checkbox" [(ngModel)]="stripUnicode" [disabled]="loading"> Strip Invisible Unicode
              <a href="https://www.google.com/search?q=Strip+Invisible+Unicode" target="_blank" title="Strip Invisible Unicode search" style="font-size: 12px; margin-left: 5px;">(?)</a>
            </label>
            <label class="checkbox-label">
              <input type="checkbox" [(ngModel)]="usePytector" [disabled]="loading"> Use Pytector
              <a href="https://pytector.readthedocs.io/en/latest/quickstart.html" target="_blank" title="Pytector Quickstart" style="font-size: 12px; margin-left: 5px;">(?)</a>
            </label>
            <label class="checkbox-label">
              <input type="checkbox" [(ngModel)]="stripQuery" [disabled]="loading"> Strip Query Params
              <a href="https://www.google.com/search?q=Strip+Query+Params" target="_blank" title="Strip Query Params search" style="font-size: 12px; margin-left: 5px;">(?)</a>
            </label>
            <label class="checkbox-label">
              <input type="checkbox" [(ngModel)]="forceOllama" [disabled]="loading"> Force Ollama
              <a href="https://ollama.com" target="_blank" title="Ollama" style="font-size: 12px; margin-left: 5px;">(?)</a>
            </label>
          </div>
        </div>

        <div *ngIf="error" class="error">
          {{ error }}
        </div>

        <div *ngIf="summary" class="result">
          <h3>Summary (Editable)</h3>
          <textarea 
            [(ngModel)]="summary" 
            class="summary-edit"
            rows="10"
            placeholder="Edit the summary here before posting..."
          ></textarea>
          <div class="char-count">
            {{ mastodonCharCount }} / 500 characters (incl. 23 for URL)
          </div>
          <div *ngIf="model" class="model-used">
            Model used: <strong>{{ model }}</strong>
            <span *ngIf="duration !== null"> (took {{ duration }}s)</span>
          </div>
          <div *ngIf="!model && duration !== null" class="model-used">
            Time taken: <strong>{{ duration }}s</strong>
          </div>
          <div class="meta">
            <small>URL: {{ lastUrl }}</small>
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
    .summary-edit {
      width: 100%;
      min-height: 150px;
      padding: 12px;
      font-size: 16px;
      line-height: 1.6;
      border: 1px solid #ddd;
      border-radius: 4px;
      resize: vertical;
      font-family: inherit;
      box-sizing: border-box;
      background-color: white;
    }
    .summary-edit:focus {
      outline: none;
      border-color: #3498db;
      box-shadow: 0 0 5px rgba(52, 152, 219, 0.2);
    }
    .char-count {
      margin-top: 6px;
      text-align: right;
      font-size: 13px;
      color: #7f8c8d;
    }
    .model-used {
      margin-top: 10px;
      font-size: 14px;
      color: #34495e;
    }
    .model-used strong {
      color: #2c3e50;
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
    .ok-btn {
      background-color: #27ae60;
    }
    .ok-btn:hover:not(:disabled) {
      background-color: #219150;
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
export class AppComponent implements AfterViewInit {
  @ViewChild('urlInput') urlInput!: ElementRef<HTMLInputElement>;
  @ViewChild('mastodonButton') mastodonButton?: ElementRef<HTMLButtonElement>;

  url = '';
  limit = 500;
  stripHidden = true;
  stripUnicode = true;
  usePytector = true;
  stripQuery = true;
  forceOllama = false;
  
  lastUrl = '';
  summary = '';
  model = '';
  duration: number | null = null;
  mastodonSuccess: boolean | null = null;
  loading = false;
  isPostingToMastodon = false;
  error = '';

  // Mastodon always counts every URL as a fixed 23 characters, plus the
  // "\n\nRead more: " footer prefix that is prepended to the URL when posting.
  private static readonly MASTODON_URL_WEIGHT = 23;
  private static readonly FOOTER_PREFIX = '\n\nRead more: ';

  get mastodonCharCount(): number {
    return this.summary.length
      + AppComponent.FOOTER_PREFIX.length
      + AppComponent.MASTODON_URL_WEIGHT;
  }

  constructor(private apiService: ApiService) {}

  ngAfterViewInit() {
    this.urlInput?.nativeElement.focus();
  }

  summarize() {
    if (!this.url) return;

    this.loading = true;
    this.error = '';
    this.summary = '';
    this.model = '';
    this.duration = null;
    this.mastodonSuccess = null;
    
    this.apiService.summarize(
      this.url, 
      this.limit, 
      this.stripHidden, 
      this.stripUnicode, 
      this.usePytector,
      this.stripQuery,
      this.forceOllama
    ).subscribe({
      next: (res) => {
        this.summary = res.summary;
        this.lastUrl = res.url;
        this.url = res.url; // Update input field with the returned URL (possibly stripped)
        this.model = res.model || '';
        this.duration = res.duration !== undefined && res.duration !== null ? res.duration : null;
        this.loading = false;
        setTimeout(() => this.mastodonButton?.nativeElement.focus());
      },
      error: (err) => {
        this.error = err.error?.detail || 'An unexpected error occurred. Please try again.';
        this.loading = false;
      }
    });
  }

  reload() {
    window.location.reload();
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
