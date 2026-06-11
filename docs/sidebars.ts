import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  tutorialSidebar: [
    'quick-start',
    {
      type: 'category',
      label: 'Python SDK',
      items: [
        'python-sdk/installation',
        'python-sdk/basic-tracing',
        'python-sdk/langgraph-integration',
        'python-sdk/llamaindex-integration',
        'python-sdk/privacy',
      ],
    },
    {
      type: 'category',
      label: 'TypeScript SDK',
      items: [
        'typescript-sdk/installation',
        'typescript-sdk/basic-tracing',
        'typescript-sdk/langchain-integration',
      ],
    },
    {
      type: 'category',
      label: 'Replay Engine',
      items: [
        'replay/overview',
        'replay/recording',
        'replay/playback',
        'replay/comparison',
      ],
    },
    {
      type: 'category',
      label: 'Backend & API',
      items: [
        'api/overview',
        'api/traces',
        'api/replay',
        'api/alerts',
      ],
    },
    {
      type: 'category',
      label: 'Examples',
      items: [
        'examples/langgraph-agent',
        'examples/llamaindex-rag',
        'examples/multi-agent',
        'examples/typescript-agent',
      ],
    },
    'best-practices',
  ],
};

export default sidebars;
