/* Various stuff yanked from Wakaba/Kareha. */

function get_cookie(name)
{
    with(document.cookie)
    {
        var regexp=new RegExp("(^|;\\s+)"+name+"=([^;]*)(;|$)");
        var hit=regexp.exec(document.cookie);
        if(hit&&hit.length>2) return unescape(hit[2]);
        else return '';
    }
}

function set_cookie(name,value,days)
{
    if(days)
    {
        var date=new Date();
        date.setTime(date.getTime()+(days*24*60*60*1000));
        var expires="; expires="+date.toGMTString();
    }
    else expires="";
    document.cookie=name+"="+escape(value)+expires+"; path=/";
}

function get_xmlhttp()
{
    var xmlhttp;
    try { xmlhttp=new ActiveXObject("Msxml2.XMLHTTP"); }
    catch(e1)
    {
        try { xmlhttp=new ActiveXObject("Microsoft.XMLHTTP"); }
        catch(e1) { xmlhttp=null; }
    }

    if(!xmlhttp && typeof XMLHttpRequest!='undefined') xmlhttp=new XMLHttpRequest();

    return(xmlhttp);
}




function show(id) {
    var s = document.getElementById(id).style;
    s.display = (s.display) ? "" : "none";
    return false;
}


function shrink(id)
{
    var textarea=document.getElementById(id).field4;
    if(textarea) {
        rows = parseInt(textarea.getAttribute("rows")) - 4;
        cols = parseInt(textarea.getAttribute("cols")) - 8;
        if (rows < 4) rows = 4;
        if (cols < 48) cols = 48;
        textarea.setAttribute("rows", rows);
        textarea.setAttribute("cols", cols);
    }
    textarea.focus();
}

function grow(id)
{
    var textarea=document.getElementById(id).field4;
    if(textarea) {
        rows = parseInt(textarea.getAttribute("rows")) + 4;
        cols = parseInt(textarea.getAttribute("cols")) + 8;
        if (rows > 20) rows = 20;
        if (cols > 80) cols = 80;
        textarea.setAttribute("rows", rows);
        textarea.setAttribute("cols", cols);
    }
    textarea.focus();
}


function insert(text, formid)
{
    if (!formid || !text)
        return;
    var textarea=document.getElementById(formid).field4;
    if(textarea)
    {
        if(textarea.createTextRange && textarea.caretPos) // IE
        {
            var caretPos=textarea.caretPos;
            caretPos.text=caretPos.text.charAt(caretPos.text.length-1)==" "?text+" ":text;
        }
        else if(textarea.setSelectionRange) // Firefox
        {
            var start=textarea.selectionStart;
            var end=textarea.selectionEnd;
            textarea.value=textarea.value.substr(0,start)+text+textarea.value.substr(end);
            textarea.setSelectionRange(start+text.length,start+text.length);
        }
        else
        {
            textarea.value+=text+" ";
        }
        textarea.focus();
    }
}

function set_inputs(form) {
    if (!form) return;
    if (form.field1 && !form.field1.value) form.field1.value = get_cookie("name");
    if (form.field2 && !form.field2.value) form.field2.value = get_cookie("link");
}


/* blah */
function highlight(post)
{
    var cells=document.getElementsByTagName("td");
    for(var i=0;i<cells.length;i++) if(cells[i].className=="highlight") cells[i].className="reply";

    var reply=document.getElementById("reply"+post);
    if(reply)
    {
        reply.className="highlight";
        return false;
    }

    return true;
}

function delete_post(board, postid)
{
    var script = document.forms[0].action;
    if(script && confirm("Are you sure you want to delete this post?")) {
        document.location = script + "?board=" + board + "&delete=" + postid;
    }
}



/* stylesheet stuff */

function set_stylesheet(styletitle)
{
    var links=document.getElementsByTagName("link");
    var found=false;
    for(var i=0;i<links.length;i++)
    {
        var rel=links[i].getAttribute("rel");
        var title=links[i].getAttribute("title");
        if(rel.indexOf("style")!=-1&&title)
        {
            links[i].disabled=true; // IE needs this to work. IE needs to die.
            if(styletitle==title) { links[i].disabled=false; found=true; }
        }
    }
    if (found) {
        set_cookie(style_cookie,styletitle,365);
    } else {
        set_preferred_stylesheet();
    }
}

function set_preferred_stylesheet()
{
    var links=document.getElementsByTagName("link");
    for(var i=0;i<links.length;i++)
    {
        var rel=links[i].getAttribute("rel");
        var title=links[i].getAttribute("title");
        if(rel.indexOf("style")!=-1&&title) links[i].disabled=(rel.indexOf("alt")!=-1);
    }
}

function get_active_stylesheet()
{
    var links=document.getElementsByTagName("link");
    for(var i=0;i<links.length;i++)
    {
        var rel=links[i].getAttribute("rel");
        var title=links[i].getAttribute("title");
        if(rel.indexOf("style")!=-1&&title&&!links[i].disabled) return title;
    }
}

function get_preferred_stylesheet()
{
    var links=document.getElementsByTagName("link");
    for(var i=0;i<links.length;i++)
    {
        var rel=links[i].getAttribute("rel");
        var title=links[i].getAttribute("title");
        if(rel.indexOf("style")!=-1&&rel.indexOf("alt")==-1&&title) return title;
    }
    return null;
}


/* hooks */

function clearSelection()
{
    if (window.getSelection)
        window.getSelection().removeAllRanges();
    else if (document.selection)
        document.selection.empty();
}



// yeesh

function preview_post(form, target)
{
    var x = get_xmlhttp();
    var req = "board=" + encodeURIComponent(form.board.value)
        //+ "&markup=" + encodeURIComponent(form.markup.value)
        + "&preview=" + encodeURIComponent(form.threadid.value)
        + "&field4=" + encodeURIComponent(form.field4.value);

    target.innerHTML = 'Loading...';
    x.open('POST', form.action);
    x.onreadystatechange = function() {
        if (x.readyState == 4)
            target.innerHTML = x.responseText;
    };
    if (x.setRequestHeader)
        x.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    x.send(req);
}

function attach_preview(form)
{
    var inputs = form.getElementsByTagName('input');
    var submit = null;
    for (var i = 0; i < inputs.length; i++) {
        if (inputs[i].type == 'submit') {
            submit = inputs[i];
            break;
        }
    }
    if (!submit) {
        // wtf kind of form is this? never mind
        return;
    }

    var preview = document.createElement('input'); // maybe this should be <button> instead
    preview.setAttribute('type', 'button');
    preview.setAttribute('value', 'Preview');
    submit.parentNode.insertBefore(preview, submit.nextSibling);
    submit.parentNode.insertBefore(document.createTextNode(' '), submit.nextSibling);
    preview.target = null;

    preview.onclick = function() {
        if (!this.target) {
            // make a div for the previewed text under the preview button
            var n = this.parentNode;
            while (n && n.nodeName && n.nodeName.toLowerCase() != 'tr' && n.nodeName.toLowerCase() != 'div')
                n = n.parentNode;
            if (!n || !n.nodeName)
                return; // I guess this button isn't in a table or something. Weird.
            if (n.nodeName.toLowerCase() == 'div') {
                // bb style hax
                this.target = document.createElement('div');
                n.appendChild(this.target);
            } else {
                var e = document.createElement('tr');
                n.parentNode.insertBefore(e, n.nextSibling);
                e.appendChild(document.createElement('td'));
                // wakaba uses a <div> inside the <td>, which i'm not doing because it seems
                // highly redundant. this might break stylesheets, but i really don't care as
                // long as the default ones work.
                this.target = document.createElement('td');
                e.appendChild(this.target);
            }
            this.target.setAttribute('class', 'replytext');
        }
        preview_post(this.form, this.target);
    };
}

// Tested and working in IE5, preview button and stylesheet cookies are both broken though.
// Also 0ch looks like garbage. Does anyone care?
function attach_replyhax(form)
{
    if(!form.threadid||form.threadid.getAttribute('value')=='0')return;
    // add some snazzy reply form behavior that vaguely resembles a particular video hosting site
    form.style.display = 'none';
    var tdiv = document.createElement('div');
    var toggle = document.createElement('textarea');
    toggle.appendChild(document.createTextNode('Reply to this thread...'));
    toggle.setAttribute('cols', 64);
    toggle.setAttribute('rows', 2);
    toggle.style.opacity = '0.5';
    tdiv.appendChild(toggle);
    toggle.targetForm = form;
    toggle.onfocus = function() {
        this.targetForm.style.display = '';
        var text = this.targetForm.getElementsByTagName('textarea');
        if (text.length) text[0].focus();
        this.parentNode.parentNode.removeChild(this.parentNode); // delete the whole div
    };
    form.parentNode.insertBefore(tdiv, form);
}


/* date manipulation */

function pluralize(n, a, s, pl) {
    n = Math.floor(n);
    if (n == 1) return a + " " + s;
    if (!pl) pl = s + "s";
    return n + " " + pl;
}

function interval(a, b) {
    var value = (a.getTime() - b.getTime()) / 1000;
    var units = [
        [60, "a", "second"],
        [60, "a", "minute"],
        [24, "an", "hour"],
        [28, "a", "day"],
        [365 / 28, "a", "month"],
        [Infinity, "a", "year"],
    ];
    var L = "", R = " ago";

    if (!Math.floor(value)) {
        return "now";
    } else if (value < 0) {
        /*
        value = -value;
        L = "in ";
        R = "";
        */
        return "now";
    }
    for (var n = 0; n < units.length; n++) {
        if (value < units[n][0])
            return L + pluralize(value, units[n][1], units[n][2]) + R;
        value /= units[n][0];
    }
    return "?";
}


function set_guard()
{
    window.onbeforeunload = function(e) {
        var textareas = document.getElementsByTagName("textarea");
        for (var i = 0; i < textareas.length; i++) {
            if (textareas[i].value) {
                textareas[i].focus();
                return 'You were writing something.';
            }
        }
        return null;
    }
}
function clear_guard() { window.onbeforeunload = null; }


window.onload=function(e)
{
    // TODO: test this stuff with Opera/IE/etc.

    // Post-hiding for text boards, a la 2channel
    var posts = document.getElementById('posts');
    if (posts) {
        var h3s = posts.getElementsByTagName('h3');
        for (var i = 0; i < h3s.length; i++) {
            var j = h3s[i];
            j.ondblclick = function() {
                var collapsed = (this.className.indexOf('collapsed') != -1);
                clearSelection();
                this.className = collapsed ? 'mouseover' : 'collapsed mouseover';
                for (var cn = this.nextSibling; cn; cn = cn.nextSibling) {
                    if (cn.style) {
                        cn.style.display = collapsed ? '' : 'none';
                    }
                }
            };
            j.onmouseover = function() {
                if (!this.className)
                    this.className = '';
                this.className += ' mouseover';
            };
            j.onmouseout = function() {
                this.className = (this.className.indexOf('collapsed') != -1) ? 'collapsed' : '';
            };
        }
    }


    // add resize arrows to the comment box for imageboards, and auto-resize on focus for text boards
    // (but not for webkit browsers that put resize handles on textareas)
    var comment = document.getElementById('commentbox');
    if (comment) {
        if (document.getElementById('reply').field4.style.resize == undefined) {
            comment.innerHTML += '<a href="javascript:shrink(\'reply\')" title="Decrease text box size" accesskey="D">&#8593;</a>';
            comment.innerHTML += '<a href="javascript:grow(\'reply\')" title="Increase text box size" accesskey="I">&#8595;</a>';
        }
    } else {
        var textareas = document.getElementsByTagName("textarea");
        if (textareas.length && textareas[0].style.resize == undefined) {
            for (var i = 0; i < textareas.length; i++) {
                // fix the default size of 10 with javascript off
                // added fix for /z/ panel 31dec08
                if (textareas[i].getAttribute("rows") != 10)
                    continue;
                textareas[i].setAttribute("rows", 5);
                textareas[i].onfocus = function() {
                    this.setAttribute("rows", 15);
                };
                textareas[i].onblur = function() {
                    if (!this.value)
                        this.setAttribute("rows", 5);
                };
            }
        }
    }


    // set all the form inputs
    var replyform = null;
    var forms = document.getElementsByTagName("form");
    var threadpage = (document.body.getAttribute('class') == 'threadpage');
    for (var i = 0; i < forms.length; i++) {
        set_inputs(forms[i]);
        if (forms[i].field4) {
            // remember this, so we know where to put quotelinks from an #i anchor later.
            // (note that, if a page has multiple forms -- i.e. text boards -- this effectively
            // finds the *last* one.)
            replyform = forms[i].id;

            // also, if this is a text board, add a preview button.
            // (XXX this onload is getting insane, need to split this file up so that imageboards
            // and textboards get their own scripts. but let's get this shit working *first*.)
            // haha this file hasn't been touched since 2008. clearly organization is unimportant here
            if (!comment) {
                attach_preview(forms[i]);
                //if (!threadpage)
                //    attach_replyhax(forms[i]);
                //^-- this sucks
            }
        }
        forms[i].onsubmit = clear_guard;
    }
    set_guard();

    // handle #123 (highlight post) and #i123 (insert >>1 link)
    var match;
    if (match=/#i([0-9]+)$/.exec(document.location.toString())) {
        insert(">>" + match[1], replyform);
    } else if (match=/#([0-9]+)$/.exec(document.location.toString())) {
        highlight(match[1]);
    }

    // tweak reflinks to highlight individual posts and write >>n references on click.
    // this could probably be optimized
    var allLinks = document.getElementsByTagName("a");
    var now = new Date();
    for (var i = 0; i < allLinks.length; i++) {
        var a = allLinks[i];
        var linkclass = a.className;
        var parentclass = a.parentNode.className;

        if (((linkclass && linkclass.indexOf("quotelink") != -1)
             || (parentclass && parentclass.indexOf("reflink") != -1))
            && (match = /#(i?)([0-9]+)$/.exec(a.getAttribute("href")))) {
            // imageboard
            // there's only one form, so this is easy
            if (match[1] == "i") {
                a.setAttribute("onclick", "insert('>>" + match[2] + "', '" + replyform + "')");
            } else {
                a.setAttribute("onclick", "highlight(" + match[2] + ")");
            }

        } else if (parentclass && parentclass.indexOf("replynum") != -1) {

            // textboard
            for (var node = a; node; node = node.parentNode) {
                var nodeclass = node.className;
                if (nodeclass && nodeclass.indexOf("thread") != -1) {
                    // at the top of the thread -- grab the form id and get out of here
                    // (note! the 'return false' is to avoid redirecting to the url, so
                    // this works on the index page, partial threads, etc.)
                    a.setAttribute("onclick", "insert('>>" + a.text + "', '"
                        + node.getElementsByTagName("form")[0].id + "');return false");
                    break;
                }
            }
        } else if (a.getAttribute("lts")) {
            var lts = new Date();
            lts.setTime(1000 * a.getAttribute("lts"));
            a.setAttribute("title", a.innerHTML);
            a.innerHTML = interval(now, lts);
        }
    }
}


var style_cookie = document.getElementsByTagName("html")[0].getAttribute("class");
if (style_cookie) {
    style_cookie += "style";
} else {
    style_cookie = "matsubastyle";
}


var cookie=get_cookie(style_cookie);
var title=cookie?cookie:get_preferred_stylesheet();
set_stylesheet(title);
