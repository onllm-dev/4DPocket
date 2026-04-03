import { Globe } from "lucide-react";

interface PlatformIconProps {
  platform: string;
  className?: string;
}

function YouTubeIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <rect width="20" height="20" rx="4" fill="#FF0000" />
      <path d="M8 6.5l5.5 3.5L8 13.5V6.5z" fill="white" />
    </svg>
  );
}

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M10 0C4.477 0 0 4.477 0 10c0 4.418 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.009-.868-.013-1.703-2.782.603-3.369-1.342-3.369-1.342-.454-1.155-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.03-2.682-.104-.254-.447-1.27.097-2.646 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0110 4.836a9.59 9.59 0 012.504.337c1.909-1.294 2.747-1.025 2.747-1.025.546 1.376.202 2.392.1 2.646.64.698 1.026 1.591 1.026 2.682 0 3.841-2.337 4.687-4.565 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C17.138 18.163 20 14.418 20 10c0-5.523-4.477-10-10-10z"
        className="fill-[#24292E] dark:fill-gray-200"
      />
    </svg>
  );
}

function RedditIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <circle cx="10" cy="10" r="10" fill="#FF4500" />
      <path
        d="M16.67 10c0-.92-.75-1.67-1.67-1.67-.46 0-.87.18-1.17.48C12.72 8.18 11.5 7.83 10.16 7.8l.58-2.72 1.88.4c.02.48.42.87.9.87.5 0 .9-.4.9-.9s-.4-.9-.9-.9c-.35 0-.65.2-.8.5l-2.1-.45a.15.15 0 00-.18.12l-.65 3.03c-1.35.03-2.56.38-3.47 1-.3-.3-.72-.5-1.17-.5-.92 0-1.67.75-1.67 1.67 0 .68.42 1.27 1.02 1.53-.02.17-.03.35-.03.52 0 2.07 2.4 3.75 5.37 3.75 2.96 0 5.37-1.68 5.37-3.75 0-.17-.01-.35-.03-.52.6-.26 1.01-.85 1.01-1.53zM7.17 11.17c0-.5.4-.9.9-.9s.9.4.9.9-.4.9-.9.9-.9-.4-.9-.9zm5.06 2.37c-.62.62-1.8.67-2.23.67-.43 0-1.61-.05-2.23-.67a.17.17 0 010-.24.17.17 0 01.24 0c.4.4 1.25.53 1.99.53s1.59-.13 1.99-.53a.17.17 0 01.24 0 .17.17 0 010 .24zm-.18-1.47a.9.9 0 110-1.8.9.9 0 010 1.8z"
        fill="white"
      />
    </svg>
  );
}

function TwitterXIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <rect width="20" height="20" rx="4" className="fill-[#000000] dark:fill-gray-200" />
      <path
        d="M11.19 9.12L15.77 4h-1.08l-3.97 4.62L7.55 4H4l4.8 6.99L4 16h1.08l4.2-4.88L12.45 16H16l-4.81-6.88zm-1.48 1.73l-.49-.7-3.88-5.55H7l3.13 4.48.49.7 4.07 5.83H13.1l-3.39-4.76z"
        className="fill-white dark:fill-gray-900"
      />
    </svg>
  );
}

function InstagramIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <defs>
        <linearGradient id="ig-grad" x1="0" y1="20" x2="20" y2="0" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#FFDC80" />
          <stop offset="25%" stopColor="#FCAF45" />
          <stop offset="50%" stopColor="#F77737" />
          <stop offset="75%" stopColor="#C13584" />
          <stop offset="100%" stopColor="#833AB4" />
        </linearGradient>
      </defs>
      <rect width="20" height="20" rx="5" fill="url(#ig-grad)" />
      <rect x="5.5" y="5.5" width="9" height="9" rx="2.5" stroke="white" strokeWidth="1.5" />
      <circle cx="10" cy="10" r="2.5" stroke="white" strokeWidth="1.5" />
      <circle cx="14" cy="6" r="0.75" fill="white" />
    </svg>
  );
}

function LinkedInIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <rect width="20" height="20" rx="3" fill="#0A66C2" />
      <path d="M6.5 8H4.5V15.5H6.5V8z" fill="white" />
      <circle cx="5.5" cy="6" r="1.25" fill="white" />
      <path
        d="M10.5 8H8.5V15.5H10.5V11.5c0-1.1.9-2 2-2s2 .9 2 2v4H16.5V11c0-1.66-1.34-3-3-3s-3 1.34-3 3V8z"
        fill="white"
      />
    </svg>
  );
}

function HackerNewsIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <rect width="20" height="20" rx="3" fill="#FF6600" />
      <text x="5" y="15" fontFamily="Verdana, sans-serif" fontSize="13" fontWeight="bold" fill="white">Y</text>
    </svg>
  );
}

function MediumIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <rect width="20" height="20" rx="3" className="fill-[#000000] dark:fill-gray-200" />
      <ellipse cx="7" cy="10" rx="3.5" ry="4.5" className="fill-white dark:fill-gray-900" />
      <ellipse cx="13.5" cy="10" rx="2" ry="4" className="fill-white dark:fill-gray-900" />
      <ellipse cx="17.5" cy="10" rx="0.75" ry="3.5" className="fill-white dark:fill-gray-900" />
    </svg>
  );
}

function SubstackIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <circle cx="10" cy="10" r="10" fill="#FF6719" />
      <circle cx="10" cy="10" r="3" fill="white" />
      <circle cx="10" cy="10" r="1" fill="#FF6719" />
    </svg>
  );
}

function SpotifyIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <circle cx="10" cy="10" r="10" fill="#1DB954" />
      <path d="M5.5 12.5c2.5-1.2 6.2-1.2 8.5 0" stroke="white" strokeWidth="1.4" strokeLinecap="round" />
      <path d="M5 10c3-1.5 7-1.5 10 0" stroke="white" strokeWidth="1.4" strokeLinecap="round" />
      <path d="M6 7.5c2.5-1 6-1 8 0" stroke="white" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function TikTokIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <rect width="20" height="20" rx="4" className="fill-[#010101] dark:fill-gray-200" />
      <path
        d="M13.5 4.5c.3 1.8 1.5 2.8 3 3v2c-1 0-2-.3-3-1v4.5c0 2.5-2 4.5-4.5 4.5S4.5 15.5 4.5 13s2-4.5 4.5-4.5c.17 0 .33 0 .5.02V11c-.17-.03-.33-.05-.5-.05-1.38 0-2.5 1.12-2.5 2.5s1.12 2.5 2.5 2.5 2.5-1.12 2.5-2.5V4.5h2z"
        fill="#69C9D0"
      />
      <path
        d="M12.5 4.5c.3 1.8 1.5 2.8 3 3v2c-1 0-2-.3-3-1v4.5c0 2.5-2 4.5-4.5 4.5S3.5 15.5 3.5 13s2-4.5 4.5-4.5c.17 0 .33 0 .5.02V11c-.17-.03-.33-.05-.5-.05-1.38 0-2.5 1.12-2.5 2.5s1.12 2.5 2.5 2.5 2.5-1.12 2.5-2.5V4.5h2z"
        fill="#EE1D52"
        opacity="0.7"
      />
    </svg>
  );
}

function MastodonIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <rect width="20" height="20" rx="4" fill="#6364FF" />
      <path
        d="M14.5 7.5c0-2.5-1.8-3.5-4.5-3.5S5.5 5 5.5 7.5v3.5c0 2.5 1.8 4 4.5 4s4.5-1.5 4.5-4v-1h-2v1c0 1.1-.9 2-2.5 2s-2.5-.9-2.5-2v-1.5h7V7.5zm-7 1V7.5c0-1.1.9-2 2.5-2s2.5.9 2.5 2V8.5h-5z"
        fill="white"
      />
    </svg>
  );
}

function StackOverflowIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <rect width="20" height="20" rx="3" fill="#F48024" />
      <rect x="6" y="13" width="8" height="1.5" fill="white" />
      <rect x="6" y="11" width="8" height="1.5" fill="white" opacity="0.7" />
      <path d="M7 9.5l7.5-3.8.6 1.3L7.6 10.8 7 9.5z" fill="white" opacity="0.85" />
      <path d="M7.5 7l6-5 1 1.1-6 5-1-1.1z" fill="white" opacity="0.6" />
    </svg>
  );
}

function ThreadsIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <rect width="20" height="20" rx="4" className="fill-[#000000] dark:fill-gray-200" />
      <path
        d="M13.5 9.2c-.1-.06-.2-.11-.3-.16C12.9 7.5 11.6 6.5 10 6.5c-1.1 0-2 .5-2.5 1.4L8.8 8.7c.3-.6.8-.9 1.4-.9.9 0 1.6.6 1.8 1.5-0.4-.1-.8-.1-1.2-.1-1.7 0-3 .9-3 2.3 0 1.4 1.1 2.2 2.5 2.2 1.1 0 2-.5 2.6-1.4.4-.6.6-1.4.6-2.1zm-1.7 2c-.3.7-.9 1.1-1.6 1.1-.8 0-1.2-.4-1.2-.9 0-.7.7-1.1 1.8-1.1.4 0 .7 0 1 .1 0 .3-.1.6-.2.8z"
        className="fill-white dark:fill-gray-900"
      />
    </svg>
  );
}

const PLATFORM_ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  youtube: YouTubeIcon,
  github: GitHubIcon,
  reddit: RedditIcon,
  twitter: TwitterXIcon,
  instagram: InstagramIcon,
  linkedin: LinkedInIcon,
  hackernews: HackerNewsIcon,
  medium: MediumIcon,
  substack: SubstackIcon,
  spotify: SpotifyIcon,
  tiktok: TikTokIcon,
  mastodon: MastodonIcon,
  stackoverflow: StackOverflowIcon,
  threads: ThreadsIcon,
};

export function PlatformIcon({ platform, className }: PlatformIconProps) {
  const Icon = PLATFORM_ICON_MAP[platform.toLowerCase()];
  if (Icon) {
    return <Icon className={className} />;
  }
  return <Globe className={className} />;
}
