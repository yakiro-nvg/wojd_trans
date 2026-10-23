# Installation

**[Download VI_PATCH.zip](https://github.com/yakiro-nvg/wojd_trans/releases/latest/download/VI_PATCH.zip)**. This is the complete player package. Do not combine it with old LIM/QFONT packages.

> **Read the risks first:** the translation loads an additional DLL and modifies text while the client is running. It may cause startup failures or crashes, or trigger anti-cheat warnings/blocking. Publisher acceptance and account safety cannot be guaranteed. This method is needed because substantial text bypasses Unreal's standard localization route; replacing language files alone cannot translate those paths. The signed game data files remain unchanged.

1. Exit the game normally and extract the entire ZIP into a separate folder.
2. Move old files starting with `~VI_PATCH` or `~VI_QFONT` outside Content\Paks.
3. Run **install.bat** and paste the actual game-folder path when prompted. Game, ZhuxianClient and Binaries\Win64 folders are accepted.
4. Start through the launcher. Exit normally and reopen if the translation requests a restart.

**Administrator access depends on the installation folder and its permissions.** If the game is in Program Files or Windows denies write access, right-click the BAT and choose **Run as administrator**. Installation, updates, verification, removal and rollback need appropriate folder access.

Update using the new package's installer while the game is closed. `verify.bat` checks installed files; `uninstall.bat` removes the patch; `rollback.bat` restores a recorded install/uninstall transaction using the ID printed by the installer. Keep backups until no longer needed. The installer never launches or closes the game and preserves files changed by another mod on a conflict.

Some content remains untranslated or awaits review, and some layouts may still overflow at particular UI scales. Include the release version, screenshot and reproduction steps when reporting a problem; redact private information before sharing logs.
