# Standards implementation notes

Findings from using various Micropub/IndieAuth clients.

This is just a rough list of stuff I came across trying to test Interpersonal and post to my own blogs.

## Providing the bearer token in two places

micropub.rocks says that providing auth in both the Authorization header and the request body violates an RFC, but Quill does this. Probably need to allow it.

## HTML, Markdown, or other content types

Some clients have an HTML editor that submits HTML post bodies. E.g. Quill has this. For Hugo, this will probably not work well unless the file it creates is called index.html (not index.md). This complicates things as we cannot set by convention that the post is always at `content/blog/post_slug/index.md`, so we will have to try to retrieve it at both filenames.

Note that our initial plan of relying on `index.md` was always just a convention that we would have to assume, as you could use `.markdown`, `.mdwn`, `.mkd`, or other extensions just for Markdown.

## Images as base64

Some clients will encode an image as base64 and submit it inside the post body with a `data:` URI instead of submitting it to the media endpoint. Quill does this for photos inserted inline in its HTML editor. Note that they are NOT submitted as mf2 media.

Bypasses Hugo's image processing stuff, so you cannot rely on it for large images. A particularly big deal for photos uploaded from mobile cameras which are gigantic.

OTOH, it side steps the issue described below, where images are provided as both photo/video/audio mf2 properties, and also linked inline.

## Inline images and mf2 properties

Images and other media might be provided in photo/video/audio mf2 properties, they might be linked inline, or they might be BOTH.

Means our Hugo theme has to check if the media item is referenced in the body. If not, append it to the body; if so, do nothing.

I guess we could also munge post content ourselves to do this, so that the Hugo theme doesn't have to account for it, although I think I like dealing with that in the theme better.
