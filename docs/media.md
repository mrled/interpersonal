# 20211201 notes on media

[Asked a question](https://chat.indieweb.org/dev/2021-12-01#t1638318424440700)
in the #indieweb-dev channel yesterday,
the answer to which gave me a better understanding of how Micropub
expects users to submit media.
The answers given and other things I found in subsequent research are recorded here.

Micropub expects servers that support media to support photos, videos, and audio.
This is what a couple of people said in chat. I also found
[Sayeth the spec](https://www.w3.org/TR/micropub/#posting-files):

> When a Micropub request includes a file, the entire request is sent in `multipart/form-data` encoding, and the file is named according to the property it corresponds with in the vocabulary, either `audio`, `video` or `photo`. A request MAY include one or more of these files.

Also an answer to a question I hadn't yet asked but would have needed to know soon:

> Note that there is no way to upload a file when the request body is JSON encoded. Instead, you can first send the photo to the Media Endpoint and then use the resulting URL in the JSON post.

I also had a subsequent question about posts and media:

> Is it expected for Micropub that the post content will not reference media directly, and the server software will just place the media before/after any text content? Is there any provision for putting an image at a certain place inside the content?

aaronpk:

> a photo post considers the text and the photo to be separate entities
> "an image at a certain place inside the content" sounds like an article
> so yes, both are possible in micropub, but they are considered different post types and the micropub request would look different
> e.g. `photo=url&content=hello+world` vs `content=hello+<img src="url">+world`

This lead me to a [list of types of `h-entry` posts'(https://indieweb.org/Micropub#h-entry),
including `note` and `article`.

## Conclusions

So it will be common for clients to submit an entry with `content` and a `photo`, but without referencing the photo in the content with either an `<a>` or an `<img>` tag. The photo must appear alongside the content. The static site generator ought to expect this.

When submitted as one form with `multipart/form-data` containing both the Micropub request containing content and also other parts containing photo/video/audio data, expect that the HTML form will use the `name` property to be `photo`, `video`, or `audio`.

As an aside, understand that a multipart HTML form
[must have a `name` for each file, but that a `filename` is optional](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Disposition#as_a_header_for_a_multipart_body)

> A `multipart/form-data` body requires a `Content-Disposition` header to provide information for each subpart of the form (e.g. for every form field and any files that are part of field data). The first directive is always `form-data`, and the header must also include a `name` parameter to identify the relevant field. Additional directives are case-insensitive and have arguments that use quoted-string syntax after the '=' sign. Multiple parameters are separated by a semi-colon (';').

E.g.:

    Content-Disposition: form-data; name="fieldName"
    Content-Disposition: form-data; name="fieldName"; filename="filename.jpg"

What that means is that you might end up with one or more e.g. `audio` attachments, which may or may not have `filename` property, and if they do have the `filename` property, the filenames may not be unique. Finally, note that this is user input, and there are significant security implications of using a `filename`, which might be malicious; see [`secure_filename()`](https://werkzeug.palletsprojects.com/en/2.0.x/utils/#werkzeug.utils.secure_filename).

This means that Interpersonal must have a way to make a unique filename from uploads, which is also secure against malicious input. Some options:

* Ignore the filename, hash the file contents, and add the appropriate extension.
* Use the file contents hash as a directory name underneath the post directory and name the file as `secure_filename()` inside that directory. This lets a non-malicious user give a filename that will be used, which is sometimes nice to be able to do.
* Rename all incoming data like Twitter does, `Photo 1.jpeg`, `Photo 2.jpeg` etc.

When submitted as a JSON encoded body, it is not possible to upload files at the same time.
Instead, Interpersonal must have a media endpoint which accepts media, and then allows posts to reference it.
[Sayeth the spec](https://www.w3.org/TR/micropub/#h-media-endpoint-error-response):

> The Media Endpoint processes the file upload, storing it in whatever backend it wishes, and generates a URL to the file. The URL SHOULD be unguessable, such as using a UUID in the path. If the request is successful, the endpoint MUST return the URL to the file that was created in the HTTP Location header, and respond with HTTP 201 Created. The response body is left undefined.
>
> ```
> HTTP/1.1 201 Created
> Location: https://media.example.com/file/ff176c461dd111e6b6ba3e1d05defe78.jpg>
> ```
>
> The Micropub client can then use this URL as the value of e.g. the "photo" property of a Micropub request.

Interpersonal's intent is to store media alongside the post that references it, not in a separate media location as described.

* Can we return a relative URI?
* As media uploads may happen _before_ post creation, we may not know the post's URI before media is uploaded, and when it is uploaded we must also return its location right away, so we cannot provide an absolute URI to the final location.
* Can we return placeholder text that we replace with the final URI once the post is uploaded?
* Worst case, we could truly just put the media in a separate location, e.g. for Hugo blogs under like `static/uploads/{file contents hash}.{file extension}`. I don't like this as it separates the media from the post, but it would work.
* Actually, I guess we could do a hybrid approach, where we store the image under its content hash inside the `static/` directory, and then symlink it to the post directory -- although I don't actually think that the Github API supports symlinks, so this might be tricky.
* Another version of the hybrid approach might be to save the upload to a temporary location in the repo like `static/uploads/...` and when the post is submitted go retrieve all the media referenced and [move/rename it](https://stackoverflow.com/questions/31563444/rename-a-file-with-github-api) to the new post directory.
