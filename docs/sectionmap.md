# Section map

Blog configurations must have a 'sectionmap' containing at least a 'default' entry.
Like this:

```yaml
---
blogs:
  - name: example
    type: built-in example
    uri: https://example.com/
    sectionmap:
      default: blog
      bookmark: bookmarks
```

This sectionmap means that by default posts will be saved in the `blog` section of the Hugo site.
That means they'll be under `content/blog/<slug>` in the git repository,
and accessible at `https://example.com/blog/<slug>` on the web.

See also the [Hugo documentation for content sections](https://gohugo.io/content-management/sections/).

This sectionmap also defines a different section for posts with the `bookmark-of` Microformats2 property.
Those posts will be under `content/bookmarks/<slug>` and `https://example.com/bookmarks/<slug>` instead.

Note that for _all_ blogs, the `default` mapping is required.
The `bookmark` mapping is optional.

In the future, we will support more mappings.
