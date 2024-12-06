# Quadify Repository Overview
This repository is a comprehensive guide and toolkit for integrating Quadify audio hardware enhancements into Raspberry Pi audio systems, initially developed by Audiophonics and subsequently enhanced by the Quadify team.

Contained within are all necessary files and instructions to equip your Raspberry Pi audio setup with Quadify’s specialised hardware, alongside a suite of tools for optimising your device for high-quality audio playback.

## Supported Systems: 
  
### For Volumio Users:
* Installation of OLED Display
* Installation of Buttons and Leds
* Installation of rotary encoder

## Key Considerations:
* This toolkit is mostly intended for new setups but it’s crafted to be forgiving enough for use on existing Volumio installations that might need repairs or adjustments post-update. While designed with our proprietary configurations in mind, it’s not exhaustively tested in every conceivable environment. Proceed with caution, understanding the risk of needing a complete system reset in extreme situations. Always ensure your data is backed up.

* This installation process preserves most standard distribution settings. Initial configurations, especially those related to system sound and volume control via Volumio's WebUi, remain necessary. 

* An active internet connection is crucial.** for the download of necessary components, as the installation cannot proceed offline.

## Usage : 
* Update package repo list
```bash
sudo apt-get update
```

* Download source files (this repository).
```bash
git clone https://github.com/theshepherdmatt/Quadify.git
```

* Enter the directory for Volumio
```bash
cd Quadify
```

* Run the installation script **as root** to install all available features
```bash
sudo bash install.sh
```

* Post-installation, a system reboot might be necessary to apply the changes effectively. You’ll be informed via command line if such an action is required.

## Installation Timeframe :
Given the diverse landscape of Linux distributions tailored for Raspberry Pi audio setups and their varying update cycles, the installation duration can significantly fluctuate. Direct compilation of certain components from their source is a necessity, affecting overall setup time. For instance, setting up OLED may take approximately 5 minutes on Volumio audio systems.

Acknowledgement: All programming and tools are kindly provided by Audiophonics.
