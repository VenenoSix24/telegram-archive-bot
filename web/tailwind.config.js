import type { Config } from 'tailwindcss'
import animate from 'tailwindcss-animate'

/**
 * 颜色皆指向 CSS 变量（见 src/themes/*.css）。
 * 每个主题独立文件，按 data-theme + data-mode 切换深浅两套 token；
 * 组件只用语义类名（bg-ink-surface 等），不感知具体主题。
 */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        gold: {
          DEFAULT: 'rgb(var(--gold) / <alpha-value>)',
          soft: 'rgb(var(--gold-soft) / <alpha-value>)',
          muted: 'rgb(var(--gold-muted) / <alpha-value>)',
        },
        ink: {
          bg: 'rgb(var(--ink-bg) / <alpha-value>)',
          surface: 'rgb(var(--ink-surface) / <alpha-value>)',
          raised: 'rgb(var(--ink-raised) / <alpha-value>)',
          line: 'rgb(var(--ink-line) / <alpha-value>)',
        },
        steam: {
          DEFAULT: 'rgb(var(--steam) / <alpha-value>)',
          dim: 'rgb(var(--steam-dim) / <alpha-value>)',
        },
        destructive: 'rgb(var(--destructive) / <alpha-value>)',
      },
      fontFamily: {
        /* 标题字体按主题切换：素材志定义 --font-display 为宋体，
           未定义的主题回退 Sora Variable（var() fallback）。 */
        display: ['var(--font-display, "Sora Variable")', '"PingFang SC"', '"Microsoft YaHei"', 'sans-serif'],
        mono: ['"SF Mono"', '"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        card: '14px',
      },
      boxShadow: {
        glow: '0 0 0 1px rgb(var(--gold) / 0.35), 0 8px 30px -12px rgb(var(--gold) / 0.25)',
      },
    },
  },
  plugins: [animate],
} satisfies Config