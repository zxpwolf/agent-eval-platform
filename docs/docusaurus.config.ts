import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Agent Trace',
  tagline: 'Observability and Replay for AI Agents',
  favicon: 'img/favicon.ico',

  url: 'https://agent-trace.dev',
  baseUrl: '/',

  organizationName: 'agent-trace',
  projectName: 'agent-observability',

  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/agent-trace/agent-observability/tree/main/docs/',
        },
        blog: {
          showReadingTime: true,
          editUrl: 'https://github.com/agent-trace/agent-observability/tree/main/docs/',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    navbar: {
      title: 'Agent Trace',
      logo: {
        alt: 'Agent Trace Logo',
        src: 'img/logo.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'tutorialSidebar',
          position: 'left',
          label: 'Documentation',
        },
        {to: '/blog', label: 'Blog', position: 'left'},
        {
          href: 'https://github.com/agent-trace/agent-observability',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            {
              label: 'Quick Start',
              to: '/docs/quick-start',
            },
            {
              label: 'Python SDK',
              to: '/docs/python-sdk',
            },
            {
              label: 'TypeScript SDK',
              to: '/docs/typescript-sdk',
            },
          ],
        },
        {
          title: 'Community',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/agent-trace/agent-observability',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Agent Trace. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['python', 'typescript', 'bash', 'json'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
