import { Tags as TagsIcon, Hash, Sparkles } from "lucide-react";
import { useTags } from "@/hooks/use-tags";

export default function Tags() {
  const { data: tags, isLoading } = useTags();

  if (isLoading) {
    return (
      <div className="animate-fade-in p-6 max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <TagsIcon className="h-6 w-6 text-sky-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Tags
          </h1>
        </div>
        <div className="space-y-4">
          <div className="h-48 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-lg" />
          <div className="h-64 animate-pulse bg-gray-200 dark:bg-gray-800 rounded-lg" />
        </div>
      </div>
    );
  }

  if (!tags || tags.length === 0) {
    return (
      <div className="animate-fade-in p-6 max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <TagsIcon className="h-6 w-6 text-sky-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Tags
          </h1>
        </div>
        <div className="text-center py-16 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm">
          <TagsIcon className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400 text-lg mb-1">
            No tags yet
          </p>
          <p className="text-sm text-gray-400 dark:text-gray-500">
            Tags are created automatically as you save content
          </p>
        </div>
      </div>
    );
  }

  const maxCount = Math.max(...tags.map((t) => t.usage_count), 1);
  const minCount = Math.min(...tags.map((t) => t.usage_count), 0);

  const getOpacity = (count: number) => {
    const ratio =
      maxCount === minCount
        ? 0.5
        : (count - minCount) / (maxCount - minCount);
    return 0.4 + ratio * 0.6;
  };

  const getFontSize = (count: number) => {
    const ratio =
      maxCount === minCount
        ? 0.5
        : (count - minCount) / (maxCount - minCount);
    return 12 + ratio * 20;
  };

  const rootTags = tags.filter((t) => !t.parent_id);
  const childTags = (parentId: string) =>
    tags.filter((t) => t.parent_id === parentId);

  return (
    <div className="animate-fade-in p-6 max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <TagsIcon className="h-6 w-6 text-sky-600" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Tags
        </h1>
      </div>

      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-6 mb-8">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-400 mb-4">
          Tag Cloud
        </h2>
        <div className="flex flex-wrap gap-2.5 items-center">
          {tags.map((tag) => (
            <span
              key={tag.id}
              title={`${tag.usage_count} items`}
              style={{
                fontSize: `${getFontSize(tag.usage_count)}px`,
                opacity: getOpacity(tag.usage_count),
              }}
              className="px-3 py-1 rounded-full bg-sky-50 dark:bg-sky-900/20 text-sky-600 cursor-default transition-all duration-200 hover:shadow-md"
            >
              {tag.name}
            </span>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm overflow-hidden">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-400 px-5 py-4 border-b border-gray-100 dark:border-gray-800">
          All Tags
        </h2>
        <ul className="divide-y divide-gray-100 dark:divide-gray-800">
          {rootTags.map((tag) => (
            <li key={tag.id}>
              <div className="flex items-center justify-between px-5 py-3">
                <div className="flex items-center gap-2.5">
                  <Hash className="h-4 w-4 text-gray-400" />
                  {tag.color && (
                    <span
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ backgroundColor: tag.color }}
                    />
                  )}
                  <span className="font-medium text-gray-900 dark:text-gray-100 text-sm">
                    {tag.name}
                  </span>
                  {tag.ai_generated && (
                    <span className="inline-flex items-center gap-1 text-xs text-sky-600 bg-sky-50 dark:bg-sky-900/20 px-1.5 py-0.5 rounded-full">
                      <Sparkles className="h-3 w-3" />
                      AI
                    </span>
                  )}
                </div>
                <span className="text-xs text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded-full">
                  {tag.usage_count}
                </span>
              </div>
              {childTags(tag.id).map((child) => (
                <div
                  key={child.id}
                  className="flex items-center justify-between pl-10 pr-5 py-2.5 bg-gray-50/50 dark:bg-gray-800/30"
                >
                  <div className="flex items-center gap-2.5">
                    <Hash className="h-3.5 w-3.5 text-gray-300 dark:text-gray-600" />
                    {child.color && (
                      <span
                        className="w-2 h-2 rounded-full flex-shrink-0"
                        style={{ backgroundColor: child.color }}
                      />
                    )}
                    <span className="text-sm text-gray-600 dark:text-gray-400">
                      {child.name}
                    </span>
                    {child.ai_generated && (
                      <span className="inline-flex items-center gap-1 text-xs text-sky-600 bg-sky-50 dark:bg-sky-900/20 px-1.5 py-0.5 rounded-full">
                        <Sparkles className="h-3 w-3" />
                        AI
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded-full">
                    {child.usage_count}
                  </span>
                </div>
              ))}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
