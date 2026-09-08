from typing import TypedDict


class _AppConfigRequired(TypedDict):
    pkg: str
    name: str
    patch_source: str | list[str]
    arch: str
    icon: str


class AppConfig(_AppConfigRequired, total=False):
    exclude: list[str]
    enable: list[str]
    force_version: str
    force_build: str


DISPLAY_NAMES: dict[str, str] = {
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
    "tiktok-hxreborn": "TikTok",
    "warp": "1.1.1.1",
    "inshot": "InShot",
    "google-photos": "Google Photos",
    "inure-github": "inure-Github",
    "inure-play": "inure-PlayStore",
    "proton-pass": "Proton Pass",
    "notesnook": "Notesnook",
    "termius": "Termius",
    "twitter-x": "Twitter-X",
    "lara-croft-gol": "Lara Croft: GoL",
    "prince-of-persia-lost-crown": "PoP: Lost Crown",
    "altos-adventure": "Alto's Adventure",
    "altos-odyssey": "Alto's Odyssey",
    "vivaldi-snapshot": "Vivaldi Snapshot",
    "minecraft-pe-mods": "MC PE Mods",
}

APKMIRROR_APPS: list[str] = [
    "youtube",
    "youtube-music",
    "reddit",
    "twitter",
    "gboard",
    "brave",
    "proton-vpn",
    "tiktok",
    "warp",
    "inshot",
    "google-photos",
    "proton-pass",
    "notesnook",
    "termius",
    "lara-croft-gol",
    "prince-of-persia-lost-crown",
    "altos-adventure",
    "altos-odyssey",
    "vivaldi-snapshot",
    "minecraft-pe-mods",
]

APPS_CONFIG: dict[str, AppConfig] = {
    "youtube": {
        "pkg": "com.google.android.youtube",
        "name": "youtube",
        "patch_source": "morphe",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/youtube/FF0000",
        "exclude": [],
    },
    "youtube-music": {
        "pkg": "com.google.android.apps.youtube.music",
        "name": "youtube-music",
        "patch_source": "morphe",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/youtubemusic/FF0000",
        "exclude": [],
    },
    "reddit": {
        "pkg": "com.reddit.frontpage",
        "name": "reddit",
        "patch_source": "morphe",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/reddit/FF4500",
        "exclude": [],
    },
    "reddit-adobo": {
        "pkg": "com.reddit.frontpage",
        "name": "reddit",
        "patch_source": "adobo",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/reddit/FF4500",
        "exclude": [],
        "enable": ["Change package name"],
    },
    "twitter": {
        "pkg": "com.twitter.android",
        "name": "twitter",
        "patch_source": "piko",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/x/000000",
        "exclude": ["Dynamic color"],
        "enable": ["Bring back twitter", "Disunify xchat system", "Export all activities"],
    },
    "twitter-x": {
        "pkg": "com.twitter.android",
        "name": "twitter",
        "patch_source": ["piko-newx", "morphe"],
        "arch": "arm64-v8a",
        "force_version": "12.22.0-prod.01",
        "enable": ["Disable Play Store updates"],
        "icon": "https://cdn.simpleicons.org/x/000000",
    },
    "instagram": {
        "pkg": "com.instagram.android",
        "name": "instagram",
        "patch_source": "piko",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/instagram/E4405F",
    },
    "gboard": {
        "pkg": "com.google.android.inputmethod.latin",
        "name": "gboard",
        "patch_source": "jasonwu",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/google/4285F4",
        "exclude": [
            "Zhuyin Bottom Row Key Sizes",
            "Zhuyin Quick Traditional/Simplified Toggle",
            "Zhuyin Slide Input",
        ],
    },
    "speedtest": {
        "pkg": "org.zwanoo.android.speedtest",
        "name": "speedtest",
        "patch_source": "rushi",
        "arch": "arm64-v8a",
        "icon": "https://www.google.com/s2/favicons?sz=128&domain=speedtest.net",
        "exclude": [],
        "force_version": "7.0.7",
    },
    "brave": {
        "pkg": "com.brave.browser",
        "name": "brave",
        "patch_source": "dh6k",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/brave/FB542B",
        "force_version": "1.92.140",
        "exclude": [],
    },
    "proton-vpn": {
        "pkg": "ch.protonvpn.android",
        "name": "proton-vpn",
        "patch_source": "hoodles",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/protonvpn",
        "exclude": [],
    },
    "tiktok": {
        "pkg": "com.zhiliaoapp.musically",
        "name": "tiktok",
        "patch_source": ["tiktok", "morphe"],
        "arch": "arm64-v8a",
        "force_version": "46.2.3",
        "icon": "https://cdn.simpleicons.org/tiktok",
        "exclude": [],
        "enable": ["Disable Play Store updates"],
    },
    "tiktok-hxreborn": {
        "pkg": "com.zhiliaoapp.musically",
        "name": "tiktok",
        "patch_source": ["hxreborn-tiktok", "morphe"],
        "arch": "arm64-v8a",
        "force_version": "46.2.3",
        "icon": "https://cdn.simpleicons.org/tiktok",
        "exclude": [],
        "enable": ["Disable Play Store updates"],
    },
    "warp": {
        "pkg": "com.cloudflare.onedotonedotonedotone",
        "name": "warp",
        "patch_source": "rushi",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/1dot1dot1dot1",
        "exclude": ["Disable SSL Pinning"],
    },
    "inshot": {
        "pkg": "com.camerasideas.instashot",
        "name": "inshot",
        "patch_source": "hooman",
        "arch": "arm64-v8a",
        "icon": "https://www.google.com/s2/favicons?sz=128&domain=inshot.com",
        "exclude": [],
    },
    "google-photos": {
        "pkg": "com.google.android.apps.photos",
        "name": "google-photos",
        "patch_source": "rushi",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/googlephotos",
        "exclude": [],
        "enable": [
            "AMOLED dark theme",
            "Change package name",
            "Enable DCIM folders backup control",
            "Fix DCIM folder classification",
            "Spoof features",
            "GmsCore support",
        ],
    },
    "inure-github": {
        "pkg": "app.simple.inure",
        "name": "inure-github",
        "patch_source": "rushi",
        "arch": "arm64-v8a",
        "icon": "https://files.svgcdn.io/arcticons/inure.svg",
        "exclude": [],
    },
    "inure-play": {
        "pkg": "app.simple.inure.play",
        "name": "inure-play",
        "patch_source": "rushi",
        "arch": "arm64-v8a",
        "icon": "https://files.svgcdn.io/arcticons/inure.svg",
        "exclude": [],
    },
    "proton-pass": {
        "pkg": "proton.android.pass",
        "name": "proton-pass",
        "patch_source": "rushi",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/protonpass",
        "exclude": [],
    },
    "notesnook": {
        "pkg": "com.streetwriters.notesnook",
        "name": "notesnook",
        "patch_source": "hxreborn",
        "arch": "arm64-v8a",
        "icon": "https://www.google.com/s2/favicons?sz=128&domain=notesnook.com",
        "exclude": [],
    },
    "termius": {
        "pkg": "com.server.auditor.ssh.client",
        "name": "termius",
        "patch_source": "rushi",
        "arch": "arm64-v8a",
        "icon": "https://www.google.com/s2/favicons?sz=128&domain=termius.com",
        "exclude": [],
    },
    "lara-croft-gol": {
        "pkg": "com.feralinteractive.laracroftgol_android",
        "name": "lara-croft-gol",
        "patch_source": "miguel",
        "arch": "arm64-v8a",
        "icon": "https://downloadr2.apkmirror.com/wp-content/uploads/2026/01/18/697d152e0cf3c_com.feralinteractive.laracroftgol_android-384x384.png",
        "exclude": [],
    },
    "prince-of-persia-lost-crown": {
        "pkg": "com.ubisoft.princeofpersia.thelostcrown.mobile.action.adventure.platform",
        "name": "prince-of-persia-lost-crown",
        "patch_source": "okish",
        "arch": "arm64-v8a",
        "icon": "https://downloadr2.apkmirror.com/wp-content/uploads/2025/04/30/67fca16044b6b_com.ubisoft.princeofpersia.thelostcrown.mobile.action.adventure.platform-384x384.png",
        "exclude": [],
    },
    "altos-adventure": {
        "pkg": "com.noodlecake.altosadventure",
        "name": "altos-adventure",
        "patch_source": "okish",
        "arch": "arm64-v8a",
        "icon": "https://downloadr2.apkmirror.com/wp-content/uploads/2018/09/5ba11f323acd8-384x384.png",
        "exclude": [],
    },
    "altos-odyssey": {
        "pkg": "com.noodlecake.altosodyssey",
        "name": "altos-odyssey",
        "patch_source": "okish",
        "arch": "arm64-v8a",
        "icon": "https://downloadr2.apkmirror.com/wp-content/uploads/2020/07/96/5f1b0fa2c0f2c-384x384.png",
        "exclude": [],
    },
    "vivaldi-snapshot": {
        "pkg": "com.vivaldi.browser.snapshot",
        "name": "vivaldi-snapshot",
        "patch_source": "kveld",
        "arch": "arm64-v8a",
        "icon": "https://downloadr2.apkmirror.com/wp-content/uploads/2023/10/19/652f7f4248aae_com.vivaldi.browser.snapshot-384x384.png",
        "exclude": [],
    },
    "minecraft-pe-mods": {
        "pkg": "com.ultimategamestudio.mcpecenter.mods",
        "name": "minecraft-pe-mods",
        "patch_source": "alastor",
        "arch": "arm64-v8a",
        "icon": "https://downloadr2.apkmirror.com/wp-content/uploads/2023/08/66/64f1be78c1024_com.ultimategamestudio.mcpecenter.mods-384x384.png",
        "exclude": [],
    },
}

PROCESS_ORDER: list[str] = [
    "youtube",
    "youtube-music",
    "reddit",
    "reddit-adobo",
    "twitter",
    "twitter-x",
    "instagram",
    "gboard",
    "speedtest",
    "brave",
    "proton-vpn",
    "tiktok",
    "tiktok-hxreborn",
    "warp",
    "inshot",
    "google-photos",
    "inure-github",
    "inure-play",
    "proton-pass",
    "notesnook",
    "termius",
    "lara-croft-gol",
    "prince-of-persia-lost-crown",
    "altos-adventure",
    "altos-odyssey",
    "vivaldi-snapshot",
    "minecraft-pe-mods",
]

PATCH_SOURCES: dict[str, tuple[str, str, str]] = {
    "morphe": ("MorpheApp", "morphe-patches", "🟢 Morphe"),
    "piko": ("crimera", "piko", "✖️ Piko"),
    "piko-newx": ("crimera", "piko-newx", "🆕 Piko NewX"),
    "adobo": ("jkennethcarino", "adobo", "🥘 Adobo"),
    "rushi": ("rushiranpise", "morphe-patches", "⚡ Rushiranpise"),
    "dh6k": ("dh6k", "morphe-patches", "🦁 dh6k"),
    "hoodles": ("hoo-dles", "morphe-patches", "🍃 hoo-dles"),
    "tiktok": ("icysymmetra", "tiktok-patches-for-morphe", "🎵 TikTok Patches"),
    "hooman": ("arandomhooman", "hoomans-morphe-patches", "🎬 Hooman's Patches"),
    "jasonwu": ("jasonwu1994", "Gboard-patches", "⌨️ JasonWu Gboard"),
    "hxreborn": ("hxreborn", "morphe-patches", "🔥 hxreborn"),
    "hxreborn-tiktok": ("hxreborn", "hxreborn-tiktok-patches", "🔥 hxreborn TikTok"),
    "miguel": ("MiguelNinja19", "miguel-morphe-patches", "🥷 Miguel"),
    "okish": ("byehi98", "okish-morphe-patches", "🎮 Okish"),
    "kveld": ("kveld9", "kveld-morphe-patches", "🌙 Kveld"),
    "alastor": ("Alastor-Kaneki", "Morphe-Patches", "👹 Alastor"),
}


def patch_sources_for(app_key: str) -> list[str]:
    source = APPS_CONFIG[app_key]["patch_source"]
    return source if isinstance(source, list) else [source]


def get_release_naming(app_key: str) -> tuple[str, str | None]:
    config = APPS_CONFIG[app_key]
    display_name = DISPLAY_NAMES.get(app_key, config["name"])

    siblings = [k for k, c in APPS_CONFIG.items() if DISPLAY_NAMES.get(k, c["name"]) == display_name]
    if len(siblings) <= 1:
        return display_name, None

    primary_source = patch_sources_for(app_key)[0]
    return display_name, PATCH_SOURCES[primary_source][0]
