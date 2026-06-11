---
sidebar_position: 1
---

# TypeScript SDK Installation

## Requirements

- Node.js 18+
- npm or yarn

## Install from npm

```bash
npm install @agent-trace/sdk
```

## Install from Source

```bash
cd sdk/typescript
npm install
npm run build
```

## Verify Installation

```typescript
import { getTracer } from '@agent-trace/sdk';

const tracer = getTracer();
console.log('Agent Trace SDK loaded');
```

## Quick Example

```typescript
import { trace, getTracer, FileExporter } from '@agent-trace/sdk';

// Setup
const tracer = getTracer();
tracer.setExporter(new FileExporter('traces.jsonl'));

// Trace a function
const myFunction = trace(
  async (input: string) => {
    return await process(input);
  },
  'my_function'
);

await myFunction('test');
```
