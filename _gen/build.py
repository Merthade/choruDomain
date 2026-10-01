#!/usr/bin/env python3
"""Generate every page of getchoru.com: home, guides, guides hub, support, privacy, terms,
404, sitemap, robots, CNAME.

AlarmPlanner's gen_guides.py (alarmclockplanner.com) is the template: same page shapes,
same campaign-link rules, same analytics. One difference: the home page is generated too,
so the header, footer and analytics exist once.

Every claim about the app was checked against the 1.0 code (fb9be58) on 2026-10-01.
Change a feature, change the copy. Run: python3 _gen/build.py
"""
import html
import json
import os
import re

GEN = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(GEN)
DOMAIN = "https://getchoru.com"
APP_ID = "6812494775"
# The plain product URL, for structured data: a reference, not a click to attribute.
STORE_CANONICAL = f"https://apps.apple.com/app/id{APP_ID}"
TODAY = "2026-10-01"
MIN_IOS = "26.5"            # IPHONEOS_DEPLOYMENT_TARGET of the 1.0 build
# False until Choru is on the App Store: every download button reads "Coming soon", the
# Smart App Banner and the JSON-LD downloadUrl stay out (an App Store link to an app that
# is not out yet is a dead page). Launch day: True, rebuild, check, push.
ON_STORE = False

# ---- App Analytics campaign attribution (AlarmPlanner's rules, same provider) ----------
# Apple's campaign-link form is /app/apple-store/id<id>?pt=&ct=&mt=8, and BOTH tokens are
# required: a ct without the pt reported nothing for AlarmPlanner until 2026-08-08.
# ct: up to 30 alphanumerics and spaces. Coarse buckets on purpose: App Analytics shows a
# campaign only after 5 first-time downloads, so one token per page would show nothing.
# Per-page clicks are in PostHog instead (data-ph + location.pathname).
PROVIDER_TOKEN = "2187944"
CT_HOME = "Website_Home"      # home, support, legal, 404
CT_GUIDE = "Website_Guide"    # every /guides/ page


def store_url(campaign):
    # `&amp;`: every consumer is an HTML attribute.
    assert 0 < len(campaign) <= 30 and campaign == campaign.strip(), f"bad ct: {campaign!r}"
    return (f"https://apps.apple.com/app/apple-store/id{APP_ID}"
            f"?pt={PROVIDER_TOKEN}&amp;ct={campaign}&amp;mt=8")


# person_profiles 'identified_only' and nothing ever identifies: anonymous events, no
# profiles. persistence 'memory': no cookie and nothing in storage. No autocapture and no
# session recording: page views and the data-ph taps only. The privacy page says exactly that.
ANALYTICS = """<link rel="preconnect" href="https://eu.i.posthog.com">
<script>
    !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.async=!0,p.src=s.api_host+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="init capture register register_once register_for_session unregister opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing clear_opt_in_out_capturing startSessionRecording stopSessionRecording isSessionRecordingStarted".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);
    if (!/^(localhost|127\\.0\\.0\\.1|\\[::1\\])$/.test(location.hostname) && location.hostname !== '') {
        posthog.init('phc_ztIjBWZp495eGWUZSUprsXSLzyElBWMcf2xc65kKfE5', {
            api_host: 'https://eu.i.posthog.com',
            person_profiles: 'identified_only',
            persistence: 'memory',
            autocapture: false,
            disable_session_recording: true
        });
        posthog.register({ app_name: 'choru_web' });
    }
</script>"""

# Clicks on anything with data-ph, plus the Android vote (a click, no personal data).
PAGE_JS = """<script>
    // posthog.capture exists only after posthog.init, which is skipped on localhost: guard it,
    // so a preview click still works and no tracking call can stop the page responding.
    function track(name) {
        try {
            if (window.posthog && typeof posthog.capture === 'function') {
                posthog.capture(name, { page: location.pathname });
            }
        } catch (e) {}
    }
    document.addEventListener('click', function (e) {
        var el = e.target.closest('[data-ph]');
        if (el) track(el.getAttribute('data-ph'));
    });
    document.querySelectorAll('[data-android]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            btn.parentElement.innerHTML = '<span class="android-cta-done">Thanks. Your interest in an Android version has been noted.</span>';
            track('android_waitlist_signup');
        });
    });
</script>"""

HEADER_TPL = """<header class="site-header">
  <nav class="nav" aria-label="Main">
    <a class="nav-logo" href="/">
      <img src="/assets/apple-touch-icon.png" alt="" width="34" height="34">
      Choru
    </a>
    <div class="nav-links">
      <a href="/#features">Features</a>
      <a href="/#how-it-works">How it works</a>
      <a href="/guides/">Guides</a>
      <a href="/#faq">FAQ</a>
      {nav_cta}
    </div>
  </nav>
</header>"""

FOOTER_TPL = """<footer class="site-footer">
  <div class="container">
    <div class="footer-grid">
      <div>
        <div class="footer-brand">
          <img src="/assets/apple-touch-icon.png" alt="" width="30" height="30">
          Choru
        </div>
        <p class="footer-note">The family chore chart that does the remembering.<br>Requires iOS {min_ios} or later.</p>
      </div>
      <div class="footer-links">
        <a href="/guides/">Guides</a>
        {footer_store}
        <a href="/support/">Support</a>
        <a href="/privacy/">Privacy</a>
        <a href="/terms/">Terms</a>
        <a href="https://alarmclockplanner.com/" data-ph="crosssell_alarmplanner">Alarm Clock Planner: alarms for any date</a>
        <a href="https://ozols.dev" rel="author">Made by Emils Ozols</a>
      </div>
    </div>
    <p class="footer-note">© Emils Ozols. Apple, iPhone, and the App Store badge are trademarks of Apple Inc.</p>
  </div>
</footer>"""


SMART_BANNER = f'<meta name="apple-itunes-app" content="app-id={APP_ID}">\n' if ON_STORE else ""


def header(campaign=CT_HOME):
    nav = (f'<a class="nav-cta" href="{store_url(campaign)}" data-ph="appstore_click">Download</a>' if ON_STORE
           else '<span class="nav-cta nav-cta--soon">Coming soon</span>')
    return HEADER_TPL.format(nav_cta=nav)


def footer(campaign=CT_HOME):
    store = (f'<a href="{store_url(campaign)}" data-ph="appstore_click">App Store</a>' if ON_STORE
             else '<span class="footer-soon">App Store: coming soon</span>')
    return FOOTER_TPL.format(footer_store=store, min_ios=MIN_IOS)


def head(title, desc, canonical, og_type="article", ogtitle=None, ogdesc=None):
    ogtitle = html.escape(ogtitle or title)
    ogdesc = html.escape(ogdesc or desc)
    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{canonical}">
{SMART_BANNER}<meta name="theme-color" content="#120d1f">
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<link rel="stylesheet" href="/styles.css">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="Choru">
<meta property="og:title" content="{ogtitle}">
<meta property="og:description" content="{ogdesc}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{DOMAIN}/assets/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@ozolsdev">
<meta name="twitter:title" content="{ogtitle}">
<meta name="twitter:description" content="{ogdesc}">
<meta name="twitter:image" content="{DOMAIN}/assets/og-image.png">
{ANALYTICS}"""


def cta_band():
    inner = """<h2>Let the list do the remembering</h2>
      <p>Add the chores once. Choru brings each one back when it is due.</p>
      <div class="cta-row">
        {pill}
      </div>"""
    if not ON_STORE:
        return f'    <div class="cta-band">\n      {inner.format(pill=SOON_PILL)}\n    </div>'
    badge_img = '<span class="badge-link"><img src="/assets/appstore-badge.svg" alt="Download on the App Store" width="180" height="60"></span>'
    return (f'    <a class="cta-band" href="{store_url(CT_HOME)}" data-ph="appstore_click" aria-label="Download Choru on the App Store">\n'
            f'      {inner.format(pill=badge_img)}\n    </a>')


def ld(data):
    return f'<script type="application/ld+json">\n{json.dumps(data, indent=2, ensure_ascii=False)}\n</script>'


SOON_PILL = """<span class="soon-pill"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>Coming soon to the App Store</span>"""


def badge(campaign, label="Download Choru on the App Store"):
    if not ON_STORE:
        return SOON_PILL
    return f"""<a class="badge-link" href="{store_url(campaign)}" data-ph="appstore_click" aria-label="{label}">
          <img src="/assets/appstore-badge.svg" alt="Download on the App Store" width="180" height="60">
        </a>"""


def figure(src, alt, caption):
    return f"""<figure>
  <img class="screen" src="/assets/{src}" alt="{html.escape(alt)}" loading="lazy" width="640" height="1284">
  <figcaption>{caption}</figcaption>
</figure>"""


def write(rel, text):
    path = os.path.join(SITE, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("wrote", rel)


def plain(s):
    """Visible text of a snippet, for structured data."""
    return html.unescape(re.sub(r"<[^>]+>", "", " ".join(s.split())))


# =========================================================================================
# GUIDES
# =========================================================================================
PAGES = [
# ---------------------------------------------------------------- partner
dict(
slug="split-chores-with-partner",
title="How to Split Chores Fairly With Your Partner",
meta="Fair is not 50/50 on every task. How to list the chores nobody sees, split them by time and taste, and keep it fair without keeping score.",
h1="How to Split Chores Fairly With Your Partner",
lede="Most chore arguments are not really about the dishes. They are about the jobs one person quietly does and the other never sees. Here is a split that holds up past the first month.",
card="List the chores nobody sees, split by time and taste, and stop keeping score.",
quick="""<strong>Quick answer:</strong> Write down every chore, including the ones that only come round every few months. Split them by how long they take and who minds them least, not one for one. Then keep the list where you both see it, so nobody has to be the one who remembers. A shared chore app like <a href="/">Choru</a> does the remembering: each chore comes back on both phones when it is due.""",
body=f"""
<h2>Start with the whole list, not the obvious one</h2>
<p>Ask two people to list the household chores and you often get two different lists. Dishes, laundry and the trash make both. The oven, the fridge shelves, the bathroom fan, the kettle that needs descaling and the dentist appointments usually make only one. Whoever wrote the longer list is usually the one feeling the load.</p>
<p>So write it all down together, in one sitting. If a job has ever made one of you sigh, it goes on the list.</p>

<h2>Split by time and taste, not one for one</h2>
<p>Fair does not mean every chore is cut in half. It means the total feels even. A few things help:</p>
<ul>
  <li><strong>Weigh by time.</strong> Ten minutes of taking out the trash is not an hour of ironing. Count how long each chore takes and how often it comes round.</li>
  <li><strong>Trade on taste.</strong> One of you hates vacuuming, the other hates the dishes. Swap. The chore nobody minds is the cheapest one to do.</li>
  <li><strong>Own it end to end.</strong> Whoever owns a chore also remembers it. "I'll do it if you remind me" is half a chore, and the other half is the annoying one.</li>
  <li><strong>Keep a shared pile.</strong> Some jobs belong to whoever has a free moment. That works, as long as you can both see them.</li>
</ul>

<h2>Make it visible, so nobody keeps score in their head</h2>
<p>A split often breaks not because someone refuses to help, but because the list lives in one person's head. They notice the oven is due, they ask, they remind. That noticing is work too, and it is the part that builds resentment.</p>
<p>Put the list somewhere you both see it, with dates. A whiteboard works until the every-three-months jobs fall off it. A shared chore app keeps those coming back on schedule, so neither of you has to be the one who remembers.</p>

<h2>How to set it up in Choru</h2>
<ol>
  <li>Add each chore and pick how often it comes back: daily, on set weekdays, weekly, monthly, quarterly, or every few days, weeks or months.</li>
  <li>Open Settings, then Family, and start a family. Your partner scans the code with their iPhone, and you both see the same list.</li>
  <li>In each chore's <strong>For</strong> row, pick whose it is: yours, your partner's, or both.</li>
  <li>Tick chores off as you do them. When a chore is on both your lists, Choru asks "Did you have help?" after the tick, so the coins go to everyone who pitched in.</li>
</ol>
{figure("shot-editor.webp", "Editing a chore in Choru: Wipe the counters, repeating daily, with a For row to pick who it belongs to and a reward of 3 coins", "Who it is for, how often it comes back, and what it pays.")}

<h2>Check in on the numbers, not the feelings</h2>
<p>Once a week, look at what actually got done. Choru's Stats count each person's chores for the week, which can settle the "I do everything" debate, one way or the other. If one side keeps coming out heavy, move a chore across. No speeches needed.</p>
{figure("shot-stats.webp", "Choru Stats with the family's chores this week, counted per person", "The week's chores, per person.")}
<div class="note-box">You each need Choru on your own iPhone, signed in to your own Apple Account. A family can have up to five people.</div>
""",
related=["share-chore-list-with-family-iphone", "chore-chart-for-kids-with-rewards", "deep-cleaning-schedule"],
cta_h="Share the chores, not the reminding",
cta_p="One list on both phones. Each chore comes back when it is due.",
),
# ---------------------------------------------------------------- kids
dict(
slug="chore-chart-for-kids-with-rewards",
title="How to Make a Chore Chart for Kids, With Rewards That Work",
meta="A kids' chore chart that lasts past week two: a short list of real jobs, coins they earn, rewards you pick together, and a quick check before it counts.",
h1="How to Make a Chore Chart for Kids That Lasts",
lede="A chore chart is easy to start and hard to keep going. The stickers run out, nobody checks it, and it turns into fridge art. Here is how to make one that lasts.",
card="Real jobs, coins they can spend, and a quick check before it counts.",
quick="""<strong>Quick answer:</strong> Give each child a short list of jobs they can finish alone, pay a few points for each, and let them spend the points on rewards you agree on together. Keep the first reward close, and check the work before the points land. In <a href="/">Choru</a>, every chore pays coins, you set the rewards and their prices, and each kid's chores, streak and coins sit together in the Kids tab.""",
body=f"""
<h2>Keep the list short and the jobs real</h2>
<p>Three to five chores a day is plenty. Pick jobs the child can finish without help, and that actually help the house: feeding the cat, setting the table, putting their laundry away, watering the plants. A list of ten turns into a list of none.</p>
<p>Younger kids can match socks or put toys back in the box. Older ones can empty the dishwasher or take out the recycling. Start easy, and add a job after a good week, not before.</p>

<h2>Points they can spend beat stickers they collect</h2>
<p>Stickers are fun until there is nothing to do with them. Points that buy something give every chore a reason. Let the kids help write the reward list, with prices: half an hour of extra screen time, picking the film, a day out. Once they have their eye on something, the chart starts running itself.</p>
<p>Keep the first prices within reach. If the first reward takes a month to earn, the chart may not last that long.</p>
<p>Streaks help too. In Choru, a streak pays bonus coins when it reaches 3, 7, 14 and 30 days, and every 30 days after that.</p>

<h2>Check it before it counts</h2>
<p>Kids work out fast that a tick is worth the same as a done chore. A quick look before the points land keeps it honest, and it is a natural moment to say well done.</p>
<p>In Choru that is a switch for each kid: <strong>Their chores need a grown-up's OK</strong>. With it on, a kid's tick shows as waiting for a grown-up to check it, and the coins land once someone approves it in the Kids tab.</p>

<h2>How to set it up in Choru</h2>
<ol>
  <li>Start a family in Settings, then Family. On the way, Choru asks the grown-ups for four digits: the parent PIN that gets any grown-up past a kid's phone lock. Skipped it? Tap your own name there later and choose Set a parent PIN.</li>
  <li>Each kid joins on their own iPhone by scanning the family's code, and marks themselves with <strong>I'm a kid</strong>.</li>
  <li>Add their chores and put them on the kid's list with the For row. Every chore pays coins, and you choose how many.</li>
  <li>Add rewards for each kid in the Kids tab, set their prices, and let the coins pile up.</li>
</ol>
{figure("shot-kids.webp", "Choru's Kids tab for Mia: a 21 day streak, her chores for today, and rewards like Pick the film for 12 coins", "Each kid's chores, streak, coins and rewards, on one screen.")}

<h2>Their own phone, locked to their own list</h2>
<p>A kid's phone locks itself to their own chores and rewards, so nobody quietly re-prices their own jobs. Any grown-up in the family can get past the lock with the parent PIN.</p>
{figure("shot-kidphone.webp", "A kid's iPhone in Choru, showing only their own chores for today and the next 7 days", "On a kid's phone: their chores, and nothing to re-price.")}
<div class="note-box">Coins are a tally inside the app, not money. What a reward is, and keeping the promise, stays between you and your kids.</div>
""",
related=["split-chores-with-partner", "share-chore-list-with-family-iphone", "deep-cleaning-schedule"],
cta_h="Chores worth saving up for",
cta_p="Coins for every chore, rewards you pick together, and a grown-up check before they count.",
),
# ---------------------------------------------------------------- deep cleaning
dict(
slug="deep-cleaning-schedule",
title="How to Keep a Deep Cleaning Schedule: Monthly, Quarterly, Yearly",
meta="The oven, the fridge shelves, the bathroom fan: the jobs that come round every few months get forgotten. A schedule that brings each one back when due.",
h1="How to Keep a Deep Cleaning Schedule",
lede="Nobody forgets the dishes. The dishes are right there in the sink, looking at you. It is the oven, the fridge shelves and the bathroom fan that sneak up on you, because nothing reminds you until they are gross.",
card="The every-few-months jobs, a schedule to start from, and what to do when you miss one.",
quick="""<strong>Quick answer:</strong> List the jobs you only do every few weeks or months, give each one its own rhythm, and keep them somewhere that tells you when each is due. Spread them out so no weekend gets all of them. A chore app like <a href="/">Choru</a> repeats each job on its own schedule, and a missed one carries over to today instead of quietly disappearing.""",
body=f"""
<h2>Why the rare jobs get forgotten</h2>
<p>Daily chores run on habit and weekly ones on routine. Anything rarer has neither. There is no trigger, so it gets done when someone notices, which is usually when it has turned into a bigger job than it needed to be.</p>

<h2>A schedule to start from</h2>
<p>Every home is different, so treat this as a first draft and adjust as you go:</p>
<ul>
  <li><strong>Every 2 weeks:</strong> change the bed sheets, clean the shower screen, wipe out the microwave.</li>
  <li><strong>Monthly:</strong> clean the fridge shelves, wash the trash cans, dust the baseboards, run the washing machine's cleaning cycle, if it has one.</li>
  <li><strong>Every 3 months:</strong> clean the oven, descale the kettle, vacuum under the sofa, wash the shower curtain.</li>
  <li><strong>Every 6 months:</strong> rotate the mattress, wash the pillows and the duvet, clean the bathroom fan cover, clear out the freezer.</li>
  <li><strong>Once a year:</strong> wash the windows inside and out, wash the curtains, clear the gutters.</li>
</ul>
<p>Then spread them out. Put the oven in January, April, July and October, and the windows in spring. If everything lands on the same weekend, the schedule becomes a punishment, and it will not last.</p>

<h2>Give every job its own rhythm</h2>
<p>The trick is that each chore repeats on its own clock. In <a href="/">Choru</a>:</p>
<ol>
  <li>Add the chore, for example <em>Clean the oven</em>.</li>
  <li>Under Repeat, pick Quarterly, or Custom for a rhythm like every 6 weeks or every 6 months.</li>
  <li>Pick the day it starts, and tag it with the room, like Kitchen.</li>
  <li>Save. It waits quietly until it is due, then shows up on that day's list.</li>
</ol>
<p>Some jobs do not need a fixed date. Make those anytime tasks instead: tick one off whenever you get to it, and it comes back a month, three months, six months or a year later.</p>
{figure("shot-chores.webp", "Choru's Chores tab: chores due today and in the next 7 days, each showing its repeat, like every 2 weeks or weekly", "Each chore keeps its own rhythm and shows when it is next due.")}

<h2>When you miss one</h2>
<p>You will. Life happens. On a paper schedule, a missed job is simply gone until someone remembers. In Choru it carries over to today as one row, with how late it is, so the oven that was due three weeks ago is still there, asking politely.</p>
{figure("shot-mess.webp", "Choru's calendar with three overdue chores carried over to today, and Choru the dragon under a pile of mess", "Missed chores carry over to today, showing how late they are.")}

<h2>See the month ahead</h2>
<p>Pull the week calendar down to open the whole month. A heavy weekend is easier to dodge when you can see it coming.</p>
""",
related=["chores-in-reminders-app", "split-chores-with-partner", "share-chore-list-with-family-iphone"],
cta_h="Every chore back on its own schedule",
cta_p="Daily to yearly repeats, and a missed chore carries over instead of disappearing.",
),
# ---------------------------------------------------------------- reminders
dict(
slug="chores-in-reminders-app",
title="Can You Use the iPhone Reminders App for Chores?",
meta="The built-in Reminders app can repeat chores and share a list with your family. What it does well, where it falls short for a household, and when a chore app fits better.",
h1="Can You Use the iPhone Reminders App for Chores?",
lede="It is already on your phone, it syncs through iCloud, and it can repeat. So why not run the house on the built-in Reminders app? For some homes it is enough. Here is how to tell.",
card="What the built-in app handles well, where it falls short, and when that matters.",
quick="""<strong>Quick answer:</strong> Yes, for a simple list. The built-in Reminders app can repeat a reminder, share a list with family through iCloud, and assign items to people on that list. What it does not do is keep any kind of score: no streaks, no coins or rewards for kids, and nothing that adds up who did what. If you want those, a chore app like <a href="/">Choru</a> fits better.""",
body=f"""
<h2>What the Reminders app does well</h2>
<ul>
  <li><strong>Repeats.</strong> Daily, weekly, monthly, yearly, or a custom rhythm like every 3 weeks.</li>
  <li><strong>Shared lists.</strong> Share a list with people through iCloud, and everyone can add and tick items.</li>
  <li><strong>Assigning.</strong> In a shared list, you can assign a reminder to one person.</li>
  <li><strong>It is already there.</strong> Nothing new to install or learn.</li>
</ul>

<h2>Where it falls short for chores</h2>
<p>Reminders is built to remind, and it is good at that. A household needs a little more:</p>
<ul>
  <li><strong>Nothing adds up.</strong> Ticked reminders are tucked away, and there is no view of who did what this week, which is the number that matters when you split chores.</li>
  <li><strong>Nothing for kids.</strong> No points or rewards, and everyone on a shared list can edit everything on it.</li>
  <li><strong>One alert per chore.</strong> Each dated reminder alerts on its own, so a long chore list means a lot of alerts, or none if you switch them off.</li>
  <li><strong>No streaks.</strong> Nothing marks a good week.</li>
</ul>

<h2>If you stick with Reminders</h2>
<ol>
  <li>Make a new list called Chores and share it with your family.</li>
  <li>Add each chore with a date, and set Repeat to its rhythm.</li>
  <li>Assign each chore to a person.</li>
  <li>Now and then, turn on Show Completed to see what got done.</li>
</ol>
<p>For a couple with a short list, that works well.</p>

<h2>What a chore app adds</h2>
<p><a href="/">Choru</a> starts from the same idea, a shared list that repeats, and adds the household parts on top:</p>
<ul>
  <li>One daily notification with what is due, instead of one per chore.</li>
  <li>Missed chores carry over to today as one row, with how late they are.</li>
  <li>Stats with each person's chores for the week.</li>
  <li>Coins for every chore, rewards you price yourself, and a Kids tab.</li>
  <li>A streak, with rest days and days away so a day off does not break it.</li>
</ul>
{figure("shot-done.webp", "Choru's calendar with today's chores all ticked and Choru the dragon resting", "All done. Choru can rest now.")}
""",
related=["deep-cleaning-schedule", "share-chore-list-with-family-iphone", "chore-chart-for-kids-with-rewards"],
cta_h="A shared list that keeps score, gently",
cta_p="Repeats, carry-over, coins and streaks, shared with your family.",
),
# ---------------------------------------------------------------- sharing
dict(
slug="share-chore-list-with-family-iphone",
title="How to Share a Chore List With Your Family on iPhone",
meta="Three ways to share the household chores with your family on iPhone, from a shared note to a family chore app, and what each one is good for.",
h1="How to Share a Chore List With Your Family on iPhone",
lede="A chore list only works if everyone can see it. The fridge door works until someone is not at home. Here are three ways to put the list on your family's iPhones, and what each is good for.",
card="A shared note, a shared Reminders list, or a family chore app, and what each is good for.",
quick="""<strong>Quick answer:</strong> For a one-off list, share a checklist in the built-in Notes app or a list in Reminders. For chores that repeat and belong to someone, use a family chore app. In <a href="/">Choru</a>, start a family in Settings, show the code, and each person scans it with their own iPhone. Everyone then sees the shared chores on their own phone.""",
body=f"""
<h2>1. A shared note</h2>
<p>Quick and free. Share a checklist in the Notes app, and everyone can tick items off. It falls apart with chores that repeat: a ticked item stays ticked until somebody unticks it, and the note cannot tell you when a job is due again.</p>

<h2>2. A shared list in Reminders</h2>
<p>Better. The built-in Reminders app can repeat, and in a shared list you can assign items to people. For a couple with a short list, it works. What it lacks is any tally of who did what, and anything for kids. There is a <a href="/guides/chores-in-reminders-app/">longer look at Reminders for chores</a>.</p>

<h2>3. A family chore app</h2>
<p>A chore app keeps the repeats, gives each chore a person, and keeps track of what got done. Here is how it works in <a href="/">Choru</a>:</p>
<ol>
  <li>Open Choru, go to Settings, then Family, and start a family.</li>
  <li>Choru shows a code. On the other iPhone, open Choru, go to Settings, then Family, then Join a family, and point the camera at the code.</li>
  <li>That is it. Everyone now sees the family's chores on their own phone.</li>
  <li>Put a chore on someone's list with the For row when you add or edit it.</li>
</ol>
{figure("shot-family.webp", "Choru showing the family's join code to scan, with the steps for the other phone", "The other phone scans the code and joins.")}

<h2>Good to know</h2>
<ul>
  <li><strong>Up to five people.</strong> A family in Choru can have five members, each on their own iPhone with their own Apple Account.</li>
  <li><strong>Show the code, do not send it.</strong> Anyone who scans it can join. If it ever gets out, change the code: everyone already in stays in, and the old code stops working.</li>
  <li><strong>Leaving is easy.</strong> Leave from Settings, Family. Your own chores, streak and coins stay on your phone.</li>
  <li><strong>Kids can join too.</strong> A kid's phone locks itself to their own list. More in the <a href="/guides/chore-chart-for-kids-with-rewards/">kids' chore chart guide</a>.</li>
</ul>
""",
related=["split-chores-with-partner", "chore-chart-for-kids-with-rewards", "chores-in-reminders-app"],
cta_h="One chore list for the whole family",
cta_p="Start a family, show the code, and everyone sees the shared chores.",
),
]

BY_SLUG = {p["slug"]: p for p in PAGES}


def related_html(slugs):
    items = "\n".join(f'      <li><a href="/guides/{s}/">{BY_SLUG[s]["h1"]}</a></li>' for s in slugs)
    return f"""<div class="related">
    <h2>Related guides</h2>
    <ul>
{items}
    </ul>
    <p><a href="/guides/">All guides</a></p>
  </div>"""


def cta_html(h, ptext, campaign):
    if not ON_STORE:
        return f"""<div class="article-cta">
    <h2>{h}</h2>
    <p>{ptext}</p>
    <div class="cta-row">
      {SOON_PILL}
    </div>
  </div>"""
    # The ENTIRE box is one anchor (no nested links: the badge is a decorative span)
    return f"""<a class="article-cta" href="{store_url(campaign)}" data-ph="appstore_click" aria-label="Download Choru on the App Store">
    <h2>{h}</h2>
    <p>{ptext}</p>
    <div class="cta-row">
      <span class="badge-link">
        <img src="/assets/appstore-badge.svg" alt="Download on the App Store" width="180" height="60">
      </span>
    </div>
  </a>"""


def article_ld(p, canonical):
    return ld({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": p["h1"],
        "description": p["meta"],
        "image": f"{DOMAIN}/assets/og-image.png",
        "datePublished": TODAY,
        "dateModified": TODAY,
        "author": {"@type": "Person", "name": "Emils Ozols", "url": "https://ozols.dev"},
        "publisher": {"@type": "Organization", "name": "Choru",
                      "logo": {"@type": "ImageObject", "url": f"{DOMAIN}/assets/icon-512.png"}},
        "mainEntityOfPage": canonical,
    }) + "\n" + ld({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{DOMAIN}/"},
            {"@type": "ListItem", "position": 2, "name": "Guides", "item": f"{DOMAIN}/guides/"},
            {"@type": "ListItem", "position": 3, "name": p["h1"], "item": canonical},
        ],
    })


def page(title, desc, canonical, body, campaign=CT_HOME, extra_head="", og_type="article",
         ogtitle=None, ogdesc=None):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head(title, desc, canonical, og_type=og_type, ogtitle=ogtitle, ogdesc=ogdesc)}
{extra_head}
</head>
<body>

{header(campaign)}

<main>
{body}
</main>

{footer(campaign)}
{PAGE_JS}
</body>
</html>
"""


for p in PAGES:
    canonical = f"{DOMAIN}/guides/{p['slug']}/"
    body = f"""<article class="article">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">Home</a> › <a href="/guides/">Guides</a> › {p['h1']}</nav>
  <h1>{p['h1']}</h1>
  <p class="lede">{p['lede']}</p>
  <div class="quick-answer"><p>{p['quick']}</p></div>
{p['body']}
{cta_html(p['cta_h'], p['cta_p'], CT_GUIDE)}
{related_html(p['related'])}
</article>"""
    write(f"guides/{p['slug']}/index.html",
          page(p["title"], p["meta"], canonical, body, CT_GUIDE, article_ld(p, canonical)))

# =========================================================================================
# GUIDES HUB
# =========================================================================================
# Clusters with real intro copy and a FAQ of its own: AlarmPlanner's flat link-list hub sat
# "Crawled - currently not indexed" until it carried text worth indexing.
CLUSTERS = [
    ("Sharing the load",
     """Chores get easier to split once everyone can see them. These guides cover dividing the
     work between grown-ups and putting one list on everyone's iPhone.""",
     ["split-chores-with-partner", "share-chore-list-with-family-iphone"]),
    ("Kids and chores",
     """Kids do chores for the same reason grown-ups go to work: something in it for them. A short
     list of real jobs, a reward worth saving for, and a quick check before it counts.""",
     ["chore-chart-for-kids-with-rewards"]),
    ("Keeping track of it all",
     """The daily chores look after themselves. It is the ones that come round every few weeks or
     months that slip, and a list that does not repeat cannot catch them.""",
     ["deep-cleaning-schedule", "chores-in-reminders-app"]),
]
_clustered = [s for _, _, slugs in CLUSTERS for s in slugs]
assert sorted(_clustered) == sorted(BY_SLUG), (
    f"hub out of sync: missing {sorted(set(BY_SLUG) - set(_clustered))}, "
    f"unknown {sorted(set(_clustered) - set(BY_SLUG))}")

HUB_FAQ = [
    ("How do you split chores fairly?",
     """Write down every chore, including the rare ones, and split them by how long they take and
     who minds them least, rather than one for one. Then keep the list where everyone sees it, so
     nobody has to be the one who remembers.""",
     "split-chores-with-partner"),
    ("What chores can a kid do?",
     """Small jobs they can finish alone that actually help the house: feeding a pet, setting the
     table, putting laundry away, watering plants. Start with three to five a day, and add one after
     a good week.""",
     "chore-chart-for-kids-with-rewards"),
    ("How often should you deep clean?",
     """Most homes do well with a few jobs every month, a bigger set every three months, and a
     handful once or twice a year. Spread them out so no weekend gets all of them.""",
     "deep-cleaning-schedule"),
    ("Can the iPhone Reminders app track chores?",
     """It can repeat chores, share a list with your family, and assign items to people. It keeps
     no tally of who did what, and has no rewards for kids.""",
     "chores-in-reminders-app"),
    ("How do I share a chore list with my family?",
     """Share a note or a Reminders list for something simple. For repeating chores that each belong
     to someone, use a family chore app where everyone joins on their own phone.""",
     "share-chore-list-with-family-iphone"),
]


def cards(slugs):
    return "\n".join(f"""      <a class="guide-card" href="/guides/{s}/">
        <h3>{BY_SLUG[s]['h1']}</h3>
        <p>{BY_SLUG[s]['card']}</p>
        <span class="more">Read the guide</span>
      </a>""" for s in slugs)


def faq_details(items, link_text="Read the guide"):
    out = []
    for q, a, href in items:
        link = f' <a href="{href}">{link_text if not href.startswith("#") else "Get the app"}</a>' if href else ""
        out.append(f"""      <details>
        <summary>{q}</summary>
        <p>{" ".join(a.split())}{link}</p>
      </details>""")
    return "\n".join(out)


def faq_ld(items):
    return ld({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": plain(q),
                        "acceptedAnswer": {"@type": "Answer", "text": plain(a)}}
                       for q, a, _ in items],
    })


clusters_html = "\n".join(f"""  <div class="container guide-cluster">
    <h2>{h}</h2>
    <p class="cluster-intro">{" ".join(intro.split())}</p>
    <div class="guide-grid">
{cards(slugs)}
    </div>
  </div>""" for h, intro, slugs in CLUSTERS)

hub_items = [(q, a, f"/guides/{s}/") for q, a, s in HUB_FAQ]
hub_body = f"""<article class="article">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">Home</a> › Guides</nav>
  <div class="hub-head">
    <div>
      <h1>Chore Guides</h1>
      <p class="lede">Practical answers to the questions every shared household runs into, and how Choru handles each one.</p>
    </div>
    <img class="mascot" src="/assets/mascot-ready.webp" alt="" width="440" height="425">
  </div>
  <p>A lot of chore trouble comes from the same place: the list lives in somebody's head. The daily jobs survive that, because they are in plain sight. The weekly ones mostly survive it. The jobs that come round every few months do not, and neither does a fair split, because nobody can see who did what.</p>
  <p>Each guide starts with what works without any app, then the workarounds worth knowing, then how <a href="/">Choru</a> handles it. Where the honest answer is that a simpler tool is enough, the guide says so.</p>
</article>
<section style="padding-top: 0;">
{clusters_html}
</section>
<section>
  <div class="container">
    <h2>Common questions</h2>
    <div class="faq-list">
{faq_details(hub_items)}
    </div>
  </div>
</section>"""
hub_head_ld = ld({
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "name": "Chore Guides",
    "description": "Practical guides to household chores: splitting chores fairly, chore charts for kids, deep cleaning schedules, and sharing a chore list on iPhone.",
    "url": f"{DOMAIN}/guides/",
}) + "\n" + faq_ld(hub_items)
write("guides/index.html",
      page("Chore Guides: Splitting Chores, Kids' Charts, Cleaning Schedules",
           "Practical guides to household chores: splitting chores fairly, chore charts for kids, deep cleaning schedules, and sharing a chore list on iPhone.",
           f"{DOMAIN}/guides/", hub_body, CT_GUIDE, hub_head_ld))

# =========================================================================================
# HOME
# =========================================================================================
ICONS = {
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2.5"/><path d="M3 9.5h18M8 3v4M16 3v4"/><circle cx="12" cy="15" r="1.6" fill="currentColor" stroke="none"/>',
    "repeat": '<path d="M17 2l4 4-4 4"/><path d="M3 11v-1a4 4 0 014-4h14"/><path d="M7 22l-4-4 4-4"/><path d="M21 13v1a4 4 0 01-4 4H3"/>',
    "carry": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "anytime": '<path d="M4 6h16M4 12h10M4 18h7"/><path d="M17 15l2 2 3-4"/>',
    "people": '<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><path d="M16 4.6a3.2 3.2 0 010 6.8"/><path d="M18 14.3c1.8.8 3 2.7 3 5.7"/>',
    "coin": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5v9M9.5 9.5c0-1 1.1-1.8 2.5-1.8s2.5.8 2.5 1.8-1.1 1.6-2.5 1.9-2.5.9-2.5 1.9 1.1 1.8 2.5 1.8 2.5-.8 2.5-1.8"/>',
    "kid": '<circle cx="12" cy="6" r="2.6"/><path d="M12 9.5v6M8 12l4-2 4 2M9.5 21l2.5-5.5L14.5 21"/>',
    "flame": '<path d="M12 22c4 0 7-2.7 7-6.8 0-3.6-2.6-6-4.2-8.2-.5 2.1-1.5 3.3-2.8 3.9C12.4 7.5 11 4.6 8.8 2.5 8.6 6.2 5 9 5 15.2 5 19.3 8 22 12 22z"/>',
}
FEATURES = [
    ("calendar", "See what is due", "A week calendar with today's chores under it. Pull it down to see the whole month."),
    ("repeat", "Repeats that fit real chores", "Daily, on set weekdays, weekly, monthly, quarterly, or every few days, weeks, months or years."),
    ("carry", "Missed ones carry over", "A chore you missed moves to today as one row, showing how late it is. Not one copy for every day you missed."),
    ("anytime", "Anytime tasks", "For jobs with no fixed date. Tick one off and it comes back a month, three months, six months or a year later."),
    ("people", "Share the household", "Invite the family with a QR code, up to five people. Everyone sees the shared chores on their own iPhone."),
    ("coin", "Coins and rewards you pick", "Every chore pays coins. Set your own rewards and their prices, then spend the coins on them."),
    ("kid", "A Kids tab", "Each kid's chores, streak and coins in one place. Their ticks can wait for a grown-up's OK."),
    ("flame", "A streak with days off", "Clear today's list to grow the streak. Rest days and days away keep it safe, and milestones pay bonus coins."),
]
SHOTS = [
    ("shot-mess.webp", "The week calendar with three overdue chores, and Choru the dragon under a pile of mess", "Help Choru out of the mess"),
    ("shot-done.webp", "Today's chores all ticked off, and Choru the dragon resting", "One tick at a time"),
    ("shot-chores.webp", "The Chores tab: what is due today and in the next 7 days, each with its repeat", "Every chore on its own rhythm"),
    ("shot-editor.webp", "Editing a chore: its repeat, who it is for, and how many coins it pays", "Set it once, it repeats"),
    ("shot-family.webp", "The family's join code, ready for another iPhone to scan", "One family, every iPhone"),
    ("shot-kids.webp", "The Kids tab: a kid's streak, chores and rewards", "A Kids tab for the children"),
    ("shot-rewards.webp", "Rewards with their prices in coins, like an hour of screen time or a day out", "Earn coins for every chore"),
    ("shot-stats.webp", "Stats: your streak, coins, and the family's chores this week", "See what got done"),
    ("shot-widgets.webp", "Home Screen widgets with today's chores and Choru the dragon", "Home Screen widgets"),
]
HOME_FAQ = [
    ("How do I share a chore list with my family?",
     """Start a family in Choru's Settings, under Family. Choru shows a code, the other person scans it
     with their own iPhone, and everyone then sees the family's chores on their own phone. A family can
     have up to five people.""",
     "/guides/share-chore-list-with-family-iphone/"),
    ("Can a chore belong to one person?",
     """Yes. Each chore has a For row: pick one person, or several. When a chore is on more than one
     person's list, ticking it asks "Did you have help?", so the coins go to everyone who pitched in.""",
     "/guides/split-chores-with-partner/"),
    ("How do kids use Choru?",
     """Each kid joins the family on their own iPhone, and their phone locks itself to their own chores
     and rewards. The Kids tab shows every kid's chores, streak and coins, and a kid's ticks can wait
     for a grown-up's OK before the coins count.""",
     "/guides/chore-chart-for-kids-with-rewards/"),
    ("What are the coins for?",
     """Every chore you tick pays coins. You add the rewards, like picking the film or a day out, set
     their prices, and spend the coins on them. Coins are a tally inside the app, not money.""",
     "/guides/chore-chart-for-kids-with-rewards/"),
    ("What happens when a chore is missed?",
     """It carries over to today as one row, showing how late it is, instead of piling up a copy for
     every day you missed.""",
     "/guides/deep-cleaning-schedule/"),
    ("How often can a chore repeat?",
     """Daily, on set weekdays, weekly, monthly, quarterly, or a custom rhythm like every 3 days, every
     2 weeks or every 6 months. Anytime tasks with no fixed date come back a month, three months, six
     months or a year after you tick them.""",
     "/guides/deep-cleaning-schedule/"),
    ("Does a day off break my streak?",
     """Not if you plan it. Pick rest days, like Sundays, and nothing is due on them. Going away? Mark
     the days away and the streak carries across the trip.""",
     None),
    ("Where are my chores stored?",
     """On your iPhone and in your own iCloud. Choru has no account of its own, and no server of mine
     holds your chores. With iCloud Drive on, it also keeps an automatic backup copy there.""",
     "/privacy/"),
    ("Does Choru have ads, or need an account?",
     """No ads, and no account to make. Choru uses the Apple Account your iPhone is already signed in
     with.""",
     "#download"),
    ("Is there an Android version?",
     """Not at the moment: Choru is made for iPhone. If someone in your house is on Android, tap
     Register your interest at the top of this page, so I know.""",
     None),
]


def home_faq_details():
    out = []
    for q, a, href in HOME_FAQ:
        if href is None:
            link = ""
        elif href.startswith("#"):
            link = f' <a href="{href}">Get the app</a>' if ON_STORE else ""
        else:
            link = f' <a href="{href}">Learn more</a>'
        out.append(f"""      <details>
        <summary>{q}</summary>
        <p>{" ".join(a.split())}{link}</p>
      </details>""")
    return "\n".join(out)


def feature_cards():
    return "\n".join(f"""      <div class="feature-card">
        <div class="ico"><svg viewBox="0 0 24 24" aria-hidden="true">{ICONS[i]}</svg></div>
        <h3>{h}</h3>
        <p>{p}</p>
      </div>""" for i, h, p in FEATURES)


def marquee_set(hidden):
    figs = "\n".join(f"""          <figure>
            <img class="screen" src="/assets/{src}" alt="{'' if hidden else html.escape(alt)}" loading="lazy" width="640" height="1284">
            <figcaption>{cap}</figcaption>
          </figure>""" for src, alt, cap in SHOTS)
    aria = ' aria-hidden="true"' if hidden else ""
    return f"""        <div class="shots-set"{aria}>
{figs}
        </div>"""


HOME_TITLE = "Choru: Family Chore Chart and Chore Tracker for iPhone"
HOME_DESC = ("Chores come back when they are due, missed ones carry over, and kids earn coins for "
             "rewards you pick. One shared chore chart for the family, each on their own iPhone.")
HOME_OG = ("Every chore comes back when it is due. Share the list with the house, keep a streak, "
           "and spend the coins on rewards you pick.")
STORE = store_url(CT_HOME)

home_body = f"""
<!-- ============ HERO ============ -->
<section class="hero" id="download">
  <div class="container hero-grid">
    <div>
      <span class="eyebrow">Family chore tracker for iPhone</span>
      <h1>Every chore comes back <span class="accent">when it's due</span></h1>
      <p class="hero-sub">The dishes are obvious. It's the oven, the fridge shelves and the bathroom fan that sneak up on you. Choru keeps track of the chores you do every day and the ones you do every few months, and shares the list with your family, each on their own iPhone.</p>
      <div class="cta-row">
        {badge(CT_HOME)}
        <a class="btn-secondary" href="#how-it-works">See how it works</a>
      </div>
      <div class="android-cta">Someone in the family on Android? <button type="button" class="android-link" data-android>Register your interest</button></div>
      <div class="trust-row">
        <span>Daily to yearly repeats</span>
        <span>Shared with the family</span>
        <span>Coins and rewards for kids</span>
        <span>No account, no ads</span>
      </div>
    </div>
    <div class="hero-art">
      <img class="screen" src="/assets/shot-mess.webp" alt="Choru on iPhone: the week calendar with three overdue chores, and Choru the dragon under a pile of mess" width="640" height="1284" fetchpriority="high">
    </div>
  </div>
</section>

<!-- ============ FEATURES ============ -->
<section id="features">
  <div class="container">
    <div class="section-head">
      <h2>A chore chart that does the remembering</h2>
      <p>Everything a chart on the fridge can't do, on your family's iPhones.</p>
    </div>
    <div class="feature-grid">
{feature_cards()}
    </div>
    <p class="extras"><strong>Also in the box:</strong> a tidy timer, a daily notification with what is due, Home Screen widgets, automatic iCloud backup, and Choru, a small purple dragon who shows how the day is going.</p>
  </div>
</section>

<!-- ============ SCREENSHOTS ============ -->
<section id="screenshots">
  <div class="container">
    <div class="section-head">
      <h2>See it in action</h2>
      <p>Real screens, straight from the app.</p>
    </div>
  </div>
  <div class="shots-marquee">
      <div class="shots-track">
{marquee_set(False)}
{marquee_set(True)}
      </div>
    </div>
</section>

<!-- ============ HOW IT WORKS ============ -->
<section id="how-it-works">
  <div class="container">
    <div class="section-head">
      <h2>How it works</h2>
      <p>From "when did we last clean the oven?" to a list that remembers, in three steps.</p>
    </div>
    <div class="steps">
      <div class="step">
        <div class="num">1</div>
        <h3>Add your chores</h3>
        <p>Name each chore, pick how often it comes back, and tag the room. Start with the every-few-months jobs: they are the ones that slip.</p>
      </div>
      <div class="step">
        <div class="num">2</div>
        <h3>Bring in the family</h3>
        <p>Start a family in Settings and show the code. Everyone scans it with their own iPhone and sees the same list.</p>
      </div>
      <div class="step">
        <div class="num">3</div>
        <h3>Tick, earn, repeat</h3>
        <p>Every tick pays coins, and clearing the day's list keeps the streak going. Each chore comes back by itself when it is due again.</p>
      </div>
    </div>
  </div>
</section>

<!-- ============ GUIDES ============ -->
<section id="guides">
  <div class="container">
    <div class="section-head">
      <h2>Guides</h2>
      <p>Straight answers to the questions every shared household runs into.</p>
    </div>
    <div class="guide-grid">
{cards([p["slug"] for p in PAGES])}
    </div>
  </div>
</section>

<!-- ============ FAQ ============ -->
<section id="faq">
  <div class="container">
    <div class="section-head">
      <h2>Frequently asked questions</h2>
    </div>
    <div class="faq-list">
{home_faq_details()}
    </div>
  </div>
</section>

<!-- ============ CTA ============ -->
<section>
  <div class="container">
{cta_band()}
    <div class="android-cta android-cta--center">Someone in the family on Android? <button type="button" class="android-link" data-android>Register your interest</button></div>
  </div>
</section>
"""
home_ld = ld({
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "name": "Choru",
    "operatingSystem": f"iOS {MIN_IOS} or later",
    "applicationCategory": "HomeApplication",
    "description": "Family chore tracker for iPhone. Chores repeat on their own schedule, missed ones carry over, the list is shared with the household, and every chore earns coins for rewards you pick.",
    "url": f"{DOMAIN}/",
    "author": {"@type": "Person", "name": "Emils Ozols", "url": "https://ozols.dev"},
    "image": f"{DOMAIN}/assets/icon-512.png",
    **({"downloadUrl": STORE_CANONICAL} if ON_STORE else {}),
}) + "\n" + faq_ld(HOME_FAQ)
write("index.html", page(HOME_TITLE, HOME_DESC, f"{DOMAIN}/", home_body, CT_HOME, home_ld,
                         og_type="website", ogdesc=HOME_OG))

# =========================================================================================
# SUPPORT / PRIVACY / TERMS (ported from ozols.dev/choru/, which stays live: the 1.0 app
# and its listing link there. Move those links in a later version, then retire them.)
# =========================================================================================
LEGAL = [
dict(
slug="support",
title="Support | Choru",
meta="Support for Choru, the family chore tracker for iPhone: contact, sharing chores with your family, kids' phones, backups, and deleting your data.",
h1="Support",
sub="Questions, problems or ideas? Every email lands in a real inbox, and I read everything.",
body="""
<div class="quick-answer"><p><strong>Email:</strong> <a href="mailto:emils@ozols.dev?subject=Choru%20support">emils@ozols.dev</a>. I usually reply within a couple of days. Choru is made by one person, so a short description of what you expected and what happened instead helps a lot.</p></div>

<h2>Frequently asked</h2>

<h3>Where are my chores stored?</h3>
<p>On your iPhone and in your own iCloud, so they appear on every device signed in to the same Apple Account. Choru has no account of its own, and no server of mine holds your chores. Choru also keeps an automatic backup copy in your iCloud Drive, under Settings, Backups. The one thing that does leave your phone is anonymous usage statistics, which you can turn off in Settings, Help out; the <a href="/privacy/">privacy policy</a> lists exactly what they contain.</p>

<h3>How do I share chores with my family?</h3>
<p>Open Settings, Family, and start a family. Choru shows a code: the other person scans it with their iPhone and joins. Everyone then sees the family's chores on their own phone. Each person needs their own Apple Account. There is a <a href="/guides/share-chore-list-with-family-iphone/">step-by-step guide</a> too.</p>

<h3>What happens if I leave a family?</h3>
<p>Your own chores, streak and coins stay on your phone. Leave from Settings, Family. If you started the family, you can remove it instead, which ends the sharing for everyone.</p>

<h3>How do I set up a phone for a kid?</h3>
<p>Choru asks for a parent PIN when you start a family. If you skipped it, tap your own name in Settings, Family and choose Set a parent PIN. When the kid joins the family, they mark themselves as a kid. A kid's phone then locks itself to their own list, and any grown-up can unlock it with the PIN.</p>

<h3>I reinstalled Choru. Where did my chores go?</h3>
<p>They come back from iCloud once Choru has synced, which can take a moment on a fresh install. If they do not, open Settings, Backups and restore the automatic copy.</p>

<h3>How do I delete my data?</h3>
<p>If you are in a family, leave it first. Then delete the app and remove its iCloud data: in the iOS Settings app, tap your name, then iCloud, manage your storage, choose Choru and delete its data.</p>

<h2>Guides</h2>
<p>For splitting chores, kids' chore charts and cleaning schedules, see the <a href="/guides/">guides</a>.</p>
""",
),
dict(
slug="privacy",
title="Privacy Policy | Choru",
meta="Privacy policy for Choru, the iPhone chore tracker. No account, no ads, anonymous opt-out usage analytics: your chores stay in your own iCloud.",
h1="Privacy Policy",
sub="Last updated: 1 October 2026",
body="""
<h2>Data storage</h2>
<p>Choru stores your chores, the days you ticked them, your streaks, coins, rewards and settings on your device and in <strong>your own private iCloud</strong>, so they appear on every device signed in to your Apple Account. There is no Choru account, and I run no server that holds your data. I cannot see it. The one thing that does leave your phone is the anonymous usage statistics described below, which you can turn off.</p>

<h2>Family sharing</h2>
<p>If you start or join a family, the family's chores are kept in iCloud by Apple and shared with the people in that family. They can see the family's chores, who ticked what, the coins and rewards, and the names in the family.</p>
<p>To tell people apart, Choru stores each person's iCloud user identifier for this app: a random string, not your email address or phone number. A kid-mode PIN is stored as a hash, not as the PIN itself.</p>
<p>A family invite is an iCloud share, shown as a code to scan. Anyone who has the code can join, so share it only with your family. You can leave a family at any time in Settings.</p>

<h2>Camera</h2>
<p>Choru asks for the camera only to scan a family's invite code. The camera image is read on your device and is not saved or sent anywhere.</p>

<h2>Notifications</h2>
<p>Reminders, and the notice that someone put a chore on your list, are created on your iPhone. They do not pass through any server of mine.</p>

<h2>Backups</h2>
<p>Choru saves automatic backup copies of your chores to your own iCloud Drive, and you can save a backup file yourself from Settings, Backups. Backups are held by Apple under your Apple Account, or wherever you save the file. They are not sent to me.</p>

<h2>Anonymous usage analytics</h2>
<p>Choru uses <strong>PostHog</strong> (hosted in the EU) to collect anonymous usage statistics, so I can see which features get used and where people get stuck. Choru carries no advertising and no advertising trackers.</p>
<p>What is collected:</p>
<ul>
  <li>Counts of what happens: chores made, ticked and unticked, rewards redeemed, timers run, backups made</li>
  <li>Which onboarding steps were viewed, and which settings were switched on or off</li>
  <li>App-level context: how many chores, rewards and tags exist, whether this phone is in a family and how many people are in it</li>
  <li>Generic device context: debug or release build, app version</li>
</ul>
<p>What is <strong>not</strong> collected:</p>
<ul>
  <li>Your name, email, or any personal identifiers</li>
  <li>What your chores say: titles, notes, the names in your family and who did what stay on your device and in your iCloud</li>
  <li>Your location, contacts, or advertising identifiers</li>
  <li>Anything linked back to you as an individual</li>
</ul>
<p><strong>A kid's phone sends nothing.</strong> Once a phone belongs to somebody marked as a kid in a family, Choru collects no usage statistics on it at all.</p>
<p>Analytics can be turned off at any time in Settings, Help out, "Share anonymous usage". The app respects it immediately.</p>

<h2>This website</h2>
<p>getchoru.com counts page views, and taps on its App Store links and a few buttons, with PostHog, hosted in the EU, so I can see which pages are useful. It sets no cookies, stores nothing on your device, and does not build a profile of you.</p>

<h2>Purchases</h2>
<p>If Choru offers purchases, Apple processes the payment. I never see your payment details.</p>

<h2>Third-party sharing</h2>
<p>I do not sell, share, or transfer your data. Apple provides iCloud, notifications and payments under Apple's own privacy policy. The only other third-party service is PostHog, for the anonymous usage statistics described above, stored on EU servers and never linked to you as an individual.</p>

<h2>Your rights</h2>
<ul>
  <li><strong>Access &amp; export</strong>: everything Choru stores is visible in the app, and you can save a backup file of it from Settings, Backups.</li>
  <li><strong>Deletion</strong>: leave any family first, then delete the app and remove Choru's data from iCloud: in the iOS Settings app, tap your name, then iCloud, manage your storage, choose Choru and delete its data.</li>
  <li><strong>Opt out of analytics</strong>: the Settings toggle above.</li>
</ul>
<p>If you are an EU/EEA resident, the GDPR grants you additional rights regarding any data processed. Choru sends me nothing that identifies you, so the only things I could hold are anonymous usage statistics and an email you send. Contact me using the email below to exercise your rights.</p>

<h2>Children's privacy</h2>
<p>Choru is made for households, children included. It does not collect personal information from anyone, children included: a kid's list lives in the family's iCloud, and a kid joins with their own Apple Account. A phone belonging to somebody marked as a kid sends no usage statistics at all.</p>

<h2>Support email</h2>
<p>If you email <a href="mailto:emils@ozols.dev">emils@ozols.dev</a>, I use your message and address only to reply. No mailing lists, no sharing.</p>

<h2>Changes</h2>
<p>If a future version of Choru changes any of the above, this page and the App Store privacy label will be updated before that version ships.</p>
""",
),
dict(
slug="terms",
title="Terms of Use | Choru",
meta="Terms of use for Choru, the iPhone chore tracker: the Yearly and Lifetime plans, renewal and cancellation, refunds, and coins.",
h1="Terms of Use",
sub="Last updated: 26 September 2026",
body="""
<p>These terms cover your use of Choru, the iPhone chore tracker made by Emils Ozols ("I", "me"). By downloading or using Choru you agree to them. If you do not agree, please do not use the app.</p>

<h2>Using Choru</h2>
<p>You may use Choru on Apple devices you own or control, for yourself and your household. Apple's <a href="https://www.apple.com/legal/internet-services/itunes/dev/stdeula/">Standard End User License Agreement</a> also applies. You may not copy, resell, reverse-engineer or redistribute the app.</p>

<h2>Plans</h2>
<p>Choru is free to download. Using it takes one of two plans:</p>
<ul>
  <li><strong>Yearly.</strong> An auto-renewable subscription, billed once a year. New subscribers can start with a free trial; its length is shown before you start.</li>
  <li><strong>Lifetime.</strong> A single payment. It is not a subscription: nothing renews and there is nothing to cancel.</li>
</ul>
<p>Both plans unlock every part of Choru. Prices are shown in the app before you buy and vary by country or region. Apple processes every payment through the App Store, tied to your Apple Account. On a new phone, "Restore purchases" on the plan screen brings your purchase back.</p>
<p>Both plans work with Apple's Family Sharing, so one purchase can cover the people in your Apple family group. Anyone who joins your family in Choru through an invite can use it without a plan of their own.</p>

<h2>Renewal and cancellation</h2>
<ul>
  <li>Payment is charged to your Apple Account when you confirm the purchase, or when the free trial ends if you started one.</li>
  <li>The Yearly plan renews automatically unless auto-renew is turned off at least 24 hours before the end of the current period. Your Apple Account is charged for the renewal within the 24 hours before the period ends.</li>
  <li>You can manage or cancel the subscription in your Apple Account settings: on iPhone, open Settings, tap your name, then Subscriptions. Cancelling stops the next renewal; the plan keeps working until the end of the period you paid for.</li>
  <li>Cancel during the free trial and you are not charged. Any unused part of a free trial ends when you buy a plan.</li>
</ul>

<h2>When a plan ends</h2>
<p>If your trial or subscription ends, your chores stay yours. They remain on your phone and in your iCloud, and you can still open Choru, look through your list and save a backup of it. Ticking chores off again takes a plan.</p>

<h2>Refunds</h2>
<p>Apple handles every payment, so I cannot issue refunds myself. You can ask Apple for one at <a href="https://reportaproblem.apple.com/">reportaproblem.apple.com</a>, under Apple's refund policy.</p>

<h2>Coins and rewards</h2>
<p>The coins you earn in Choru are a tally inside the app. They are not money: they cannot be bought, sold or exchanged, and they have no cash value. Rewards are whatever you and your family agree on, and keeping those promises is up to you, not Choru.</p>

<h2>Your chores and your family</h2>
<p>What you put into Choru is yours. It lives on your devices and in your own iCloud, as the <a href="/privacy/">privacy policy</a> describes. When you share a family, the people in it see the family's chores, who ticked what, and the coins and rewards, so invite only people you trust. A grown-up in the family is responsible for how a kid uses Choru.</p>

<h2>Acceptable use</h2>
<p>Use Choru lawfully. Do not try to disrupt it, or to reach the systems it relies on without permission.</p>

<h2>No warranty</h2>
<p>Choru is provided "as is" and "as available", without warranties of any kind, express or implied. Reminders, sync and backups depend on your device, iOS and iCloud, which are outside my control, so save a backup of anything you cannot afford to lose.</p>

<h2>Limitation of liability</h2>
<p>To the extent the law allows, I am not liable for indirect, incidental or consequential damages from using Choru or being unable to use it. Where liability cannot be excluded, it is limited to what you paid for Choru in the twelve months before the claim.</p>

<h2>Changes</h2>
<p>I may change or remove features, and update these terms. If the terms change in a meaningful way, the date at the top changes too. Using Choru after a change means you accept the updated terms.</p>

<h2>Governing law</h2>
<p>These terms are governed by the laws of Latvia and the European Union. Nothing here limits the consumer rights you have under the law of the country you live in.</p>

<h2>Contact</h2>
<p>Questions about these terms: <a href="mailto:emils@ozols.dev?subject=Choru%20terms">emils@ozols.dev</a>. For help with the app, see <a href="/support/">support</a>.</p>
""",
),
]

for lp in LEGAL:
    body = f"""<article class="article">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">Home</a> › {lp['h1']}</nav>
  <h1>{lp['h1']}</h1>
  <p class="lede">{lp['sub']}</p>
{lp['body']}
</article>"""
    write(f"{lp['slug']}/index.html", page(lp["title"], lp["meta"], f"{DOMAIN}/{lp['slug']}/", body))

# =========================================================================================
# 404, SITEMAP, ROBOTS, CNAME
# =========================================================================================
e404_body = """<article class="article" style="text-align:center; padding-top: 70px; padding-bottom: 90px;">
  <img class="mascot" src="/assets/mascot-looking.webp" alt="Choru the dragon looking through binoculars" width="409" height="440">
  <h1>404: Choru looked everywhere</h1>
  <p class="lede">This page does not exist, or it moved.</p>
  <div class="cta-row" style="justify-content: center;"><a class="btn-secondary" href="/">Back to the homepage</a><a class="btn-secondary" href="/guides/">Browse the guides</a></div>
</article>"""
write("404.html", page("Page Not Found | Choru",
                       "That page does not exist. Head back to the Choru homepage or browse the chore guides.",
                       f"{DOMAIN}/404.html", e404_body))

urls = ([f"{DOMAIN}/", f"{DOMAIN}/guides/"]
        + [f"{DOMAIN}/guides/{p['slug']}/" for p in PAGES]
        + [f"{DOMAIN}/{lp['slug']}/" for lp in LEGAL])
sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
sitemap += [f"  <url><loc>{u}</loc><lastmod>{TODAY}</lastmod></url>" for u in urls]
sitemap.append("</urlset>")
write("sitemap.xml", "\n".join(sitemap) + "\n")
write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n")
write("CNAME", "getchoru.com\n")
print(f"{len(urls)} urls in the sitemap")
