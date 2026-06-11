/**
 * Exporters for sending trace data to storage
 */

import { Trace } from './models';
import * as fs from 'fs';
import * as path from 'path';

export interface Exporter {
  export(trace: Trace): Promise<boolean>;
  flush(): Promise<void>;
}

/**
 * Console exporter (for debugging)
 */
export class ConsoleExporter implements Exporter {
  constructor(private prettyPrint: boolean = true) {}

  async export(trace: Trace): Promise<boolean> {
    if (this.prettyPrint) {
      console.log(JSON.stringify(trace, null, 2));
    } else {
      console.log(JSON.stringify(trace));
    }
    return true;
  }

  async flush(): Promise<void> {}
}

/**
 * File exporter (JSONL format)
 */
export class FileExporter implements Exporter {
  private writeStream: fs.WriteStream;

  constructor(filepath: string = 'traces.jsonl') {
    // Ensure directory exists
    const dir = path.dirname(filepath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    this.writeStream = fs.createWriteStream(filepath, { flags: 'a' });
  }

  async export(trace: Trace): Promise<boolean> {
    return new Promise((resolve) => {
      const line = JSON.stringify(trace) + '\n';
      const canContinue = this.writeStream.write(line);

      if (canContinue) {
        resolve(true);
      } else {
        this.writeStream.once('drain', () => resolve(true));
      }
    });
  }

  async flush(): Promise<void> {
    return new Promise((resolve) => {
      this.writeStream.end(() => resolve());
    });
  }

  close(): void {
    this.writeStream.end();
  }
}

/**
 * HTTP endpoint exporter
 */
export class HttpExporter implements Exporter {
  private queue: Trace[] = [];
  private flushTimer: NodeJS.Timeout | null = null;

  constructor(
    private endpoint: string = 'http://localhost:8000/api/traces',
    private apiKey?: string,
    private batchSize: number = 10,
    private flushInterval: number = 5000
  ) {}

  async export(trace: Trace): Promise<boolean> {
    this.queue.push(trace);

    if (this.queue.length >= this.batchSize) {
      await this.flushInternal();
    } else if (!this.flushTimer) {
      this.flushTimer = setTimeout(() => {
        this.flushInternal().catch(console.error);
      }, this.flushInterval);
    }

    return true;
  }

  async flush(): Promise<void> {
    if (this.flushTimer) {
      clearTimeout(this.flushTimer);
      this.flushTimer = null;
    }
    await this.flushInternal();
  }

  private async flushInternal(): Promise<void> {
    if (this.queue.length === 0) return;

    const traces = [...this.queue];
    this.queue = [];

    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (this.apiKey) {
        headers['Authorization'] = `Bearer ${this.apiKey}`;
      }

      // Send traces in parallel
      await Promise.all(
        traces.map(trace =>
          fetch(this.endpoint, {
            method: 'POST',
            headers,
            body: JSON.stringify(trace),
          }).then(res => {
            if (!res.ok) {
              throw new Error(`HTTP ${res.status}: ${res.statusText}`);
            }
          })
        )
      );
    } catch (error) {
      console.error('Failed to export traces:', error);
      // Re-add to queue on failure
      this.queue.unshift(...traces);
    }
  }
}

/**
 * Batch exporter wrapper
 */
export class BatchExporter implements Exporter {
  private buffer: Trace[] = [];
  private flushTimer: NodeJS.Timeout | null = null;

  constructor(
    private exporter: Exporter,
    private batchSize: number = 10,
    private flushInterval: number = 5000
  ) {}

  async export(trace: Trace): Promise<boolean> {
    this.buffer.push(trace);

    if (this.buffer.length >= this.batchSize) {
      await this.flushInternal();
    } else if (!this.flushTimer) {
      this.flushTimer = setTimeout(() => {
        this.flushInternal().catch(console.error);
      }, this.flushInterval);
    }

    return true;
  }

  async flush(): Promise<void> {
    if (this.flushTimer) {
      clearTimeout(this.flushTimer);
      this.flushTimer = null;
    }
    await this.flushInternal();
  }

  private async flushInternal(): Promise<void> {
    if (this.buffer.length === 0) return;

    const traces = [...this.buffer];
    this.buffer = [];

    for (const trace of traces) {
      try {
        await this.exporter.export(trace);
      } catch (error) {
        console.error('Failed to export trace:', error);
        this.buffer.unshift(trace);
      }
    }
  }
}
