# TODO

Bigger todo items that need some explication

## Describe (and prototype?) basic Hugo theme that works well with Micropub expectations

In general, Micropub should work with blogs.
However, there are some nonstandard blog things that Micropub assumes are possible.

* A photo in the properties of an h-entry should be displayed to the user when they navigate to the entry in a browser -- even if it isn't referenced in the contents.
* Micropub supports nested mf2 objects - e.g. an checkin formatted as an h-card in an h-entry blog post. micropub.rocks says that not every implementation is assumed to display this properly (but should store it properly nevertheless), but it's probably worth making a demo of how you might display it.
* Adding photos should support adding alt text, per micropub.rocks test 205.
* Should handle HTML escapes properly - when the content type is "html", do not escape, otherwise do.
