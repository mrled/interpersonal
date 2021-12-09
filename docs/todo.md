# TODO

Bigger todo items that need some explication

## Misc

* Uploads are probably not as efficient as they should be. Should I be worried about keeping the whole upload in RAM so I can hash then actually save it?

## Write a Hugo utility theme to map all URIs directly to the files that back them

Currently Interpersonal has to map URLs to files sort of hackily, by replacing `https://example.com/` with `content/` in the uri. A site could publish metadata at every url, or at some derivable location (e.g `${url}/.metadata`) that obviates this. This would be easy with Hugo, mapping all URIs directly to the files that back them. This could be saved in JSON and then referenced from anywhere.

I've also just discovered that I'll need to sometimes use `index.html` rather than `index.md`, as some posts are submitted as HTML and if Hugo is not told they are HTML, they'll get truncated or otherwise misinterpreted by Hugo's Markdown processor. This means that instead of just a single HTTP request to Github (or whatever storage backend we're using), we need to try all the `index.*` names one after the other until we find the one that we're looking for.

If we write a modular utility theme that creates a JSON data file mapping URIs to their index pages.

A guide for using this Hugo functionality is here: [Build a JSON API With Hugo's Custom Output Formats](https://forestry.io/blog/build-a-json-api-with-hugo/).

Might consider working with the authors of IndieKit and/or other static site connectors.

## Describe (and prototype?) basic Hugo theme that works well with Micropub expectations

In general, Micropub should work with blogs.
However, there are some nonstandard blog things that Micropub assumes are possible.

* `<link>` elements pointing to the IndieAuth and Micropub endpoints.
* A photo in the properties of an h-entry should be displayed to the user when they navigate to the entry in a browser -- even if it isn't referenced in the contents.
* Micropub supports nested mf2 objects - e.g. an checkin formatted as an h-card in an h-entry blog post. micropub.rocks says that not every implementation is assumed to display this properly (but should store it properly nevertheless), but it's probably worth making a demo of how you might display it.
* Adding photos should support adding alt text, per micropub.rocks test 205.
* Should handle HTML escapes properly - when the content type is "html", do not escape, otherwise do.
* Properly handle posts without titles, posts with photos but no title or content, etc
* Use image filters so that you can upload a photo from your phone's camera roll and pages will load a resized version of it so it's not too big. (Lightboxes and click-to-enlarge functionality would be nice too.)
* Frontmatter key with `photo`, `video`, and/or `audio` should be displayed even if not referenced in the content.
