DISPLAY_NAMES = {
    "youtube": "YouTube",
    "youtube-music": "YT.Music",
    "reddit": "Reddit",
    "reddit-adobo": "Reddit-Adobo",
    "twitter": "Twitter",
    "instagram": "Instagram",
    "gboard": "Gboard",
    "speedtest": "Speedtest",
    "brave": "Brave",
    "proton-vpn": "Proton VPN",
    "tiktok": "TikTok",
    "warp": "1.1.1.1",
    "inshot": "InShot",
    "google-photos": "Google Photos",
    "inure-github": "inure-Github",
    "inure-play": "inure-PlayStore",
    "waze": "Waze",
    "proton-pass": "Proton Pass",
}

APKMIRROR_APPS = [
    "youtube", "youtube-music", "reddit", "twitter",
    "gboard", "brave",
    "proton-vpn", "tiktok", "warp", "inshot", "google-photos", "waze",
    "proton-pass",
]

APPS_CONFIG = {
    "youtube": {
        "pkg": "com.google.android.youtube", "name": "youtube", "patch_source": "morphe",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/youtube/FF0000", "exclude": [],
    },
    "youtube-music": {
        "pkg": "com.google.android.apps.youtube.music", "name": "youtube-music", "patch_source": "morphe",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/youtubemusic/FF0000", "exclude": [],
    },
    "reddit": {
        "pkg": "com.reddit.frontpage", "name": "reddit", "patch_source": "morphe",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/reddit/FF4500", "exclude": [],
    },
    "reddit-adobo": {
        "pkg": "com.reddit.frontpage", "name": "reddit", "patch_source": "adobo",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/reddit/FF4500",
        "exclude": [],
        "enable": ["Change package name"],
    },
    "twitter": {
        "pkg": "com.twitter.android", "name": "twitter", "patch_source": "piko",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/x/000000",
        "exclude": ["Dynamic color"],
        "enable": ["Bring back twitter", "Disunify xchat system", "Export all activities"],
    },
    "instagram": {
        "pkg": "com.instagram.android", "name": "instagram", "patch_source": "piko",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/instagram/E4405F",
    },
    "gboard": {
        "pkg": "com.google.android.inputmethod.latin", "name": "gboard", "patch_source": "jasonwu",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/google/4285F4",
        "exclude": ["Zhuyin Bottom Row Key Sizes", "Zhuyin Quick Traditional/Simplified Toggle", "Zhuyin Slide Input"],
        
    },
    "speedtest": {
        "pkg": "org.zwanoo.android.speedtest", "name": "speedtest", "patch_source": "rushi",
        "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=speedtest.net",
        "exclude": [], "force_version": "7.0.7",
    },
    "brave": {
        "pkg": "com.brave.browser", "name": "brave", "patch_source": "bufferk",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/brave/FB542B", "exclude": [],
    },
    "proton-vpn": {
        "pkg": "ch.protonvpn.android", "name": "proton-vpn", "patch_source": "hoodles",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/protonvpn", "exclude": [],
    },
    "tiktok": {
        "pkg": "com.zhiliaoapp.musically", "name": "tiktok", "patch_source": "tiktok",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/tiktok", "exclude": [],
    },
    "warp": {
        "pkg": "com.cloudflare.onedotonedotonedotone", "name": "warp", "patch_source": "rushi",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/1dot1dot1dot1", 
        "exclude": ["Disable SSL Pinning"],
    },
    "inshot": {
        "pkg": "com.camerasideas.instashot", "name": "inshot", "patch_source": "hooman",
        "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=inshot.com", "exclude": [],
    },
    "google-photos": {
        "pkg": "com.google.android.apps.photos", "name": "google-photos", "patch_source": "rushi",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/googlephotos",
        "force_version": "7.87.0.957333026",
        "exclude": [],
        "enable": ["AMOLED dark theme", "Change package name", "Enable DCIM folders backup control", "Fix DCIM folder classification", "Spoof features", "GmsCore support"],
    },
    "inure-github": {
        "pkg": "app.simple.inure", "name": "inure-github", "patch_source": "rushi",
        "arch": "arm64-v8a", "icon": "https://files.svgcdn.io/arcticons/inure.svg",
        "exclude": [],
    },
    "inure-play": {
        "pkg": "app.simple.inure.play", "name": "inure-play", "patch_source": "rushi",
        "arch": "arm64-v8a", "icon": "https://files.svgcdn.io/arcticons/inure.svg",
        "exclude": [],
    },
    "waze": {
        "pkg": "com.waze", "name": "waze", "patch_source": "rushi",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/waze/33CCFF",
        "exclude": [],
    },
    "proton-pass": {
        "pkg": "proton.android.pass", "name": "proton-pass", "patch_source": "rushi",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/protonpass", "exclude": [],
    },
}

PROCESS_ORDER = [
    "youtube", "youtube-music", "reddit", "reddit-adobo", "twitter", "instagram",
    "gboard", "speedtest", "brave",
    "proton-vpn", "tiktok", "warp", "inshot", "google-photos", "inure-github", "inure-play", "waze",
    "proton-pass",
]

PATCH_SOURCES = {
    "morphe": ("MorpheApp", "morphe-patches", "🟢 Morphe"),
    "piko": ("crimera", "piko", "✖️ Piko"),
    "adobo": ("jkennethcarino", "adobo", "🥘 Adobo"),
    "rushi": ("rushiranpise", "morphe-patches", "⚡ Rushiranpise"),
    "bufferk": ("bufferk", "morphe-patches", "🟣 Bufferk"),
    "hoodles": ("hoo-dles", "morphe-patches", "🍃 hoo-dles"),
    "tiktok": ("icysymmetra", "tiktok-patches-for-morphe", "🎵 TikTok Patches"),
    "hooman": ("arandomhooman", "hoomans-morphe-patches", "🎬 Hooman's Patches"),
    "jasonwu": ("jasonwu1994", "Gboard-patches", "⌨️ JasonWu Gboard"),
}
