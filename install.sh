#!/bin/bash
set -e  # Exit immediately on a non-zero status (fail on error)
# set -x  # Uncomment for debugging (prints each command before execution)

# ============================================
#               Colour Definitions
# ============================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m'  # No Colour

# ============================================
#             Progress Tracking
# ============================================
TOTAL_STEPS=17
CURRENT_STEP=0
LOG_FILE="/home/${SUDO_USER:-$USER}/install.log"

# Remove any existing log file
rm -f "$LOG_FILE"

# ============================================
#              ASCII Art Banner
# ============================================
banner() {
    echo -e "${MAGENTA}"
    echo "                                                                                                                                 "
    echo "                                                                  dddddddd                                                       "
    echo "     QQQQQQQQQ     UUUUUUUU     UUUUUUUU     OOOOOOOOO          OOOOOOOOO     DDDDDDDDDDDDD      EEEEEEEEEEEEEEEEEEEEEE         "
    echo "   QQ:::::::::QQ   U::::::U     U::::::U   OO:::::::::OO      OO:::::::::OO   D::::::::::::DDD   E::::::::::::::::::::E         "
    echo " QQ:::::::::::::QQ U::::::U     U::::::U OO:::::::::::::OO  OO:::::::::::::OO D:::::::::::::::DD E::::::::::::::::::::E         "
    echo "Q:::::::QQQ:::::::QUU:::::U     U:::::UUO:::::::OOO:::::::OO:::::::OOO:::::::ODDD:::::DDDDD:::::DEE::::::EEEEEEEEE::::E        "
    echo "Q::::::O   Q::::::Q U:::::U     U:::::U O::::::O   O::::::OO::::::O   O::::::O  D:::::D    D:::::D E:::::E       EEEEEE        "
    echo "Q:::::O     Q:::::Q U:::::D     D:::::U O:::::O     O:::::OO:::::O     O:::::O  D:::::D     D:::::DE:::::E                    "
    echo "Q:::::O     Q:::::Q U:::::D     D:::::U O:::::O     O:::::OO:::::O     O:::::O  D:::::D     D:::::DE::::::EEEEEEEEEE          "
    echo "Q:::::O     Q:::::Q U:::::D     D:::::U O:::::O     O:::::OO:::::O     O:::::O  D:::::D     D:::::DE:::::::::::::::E          "
    echo "Q:::::O     Q:::::Q U:::::D     D:::::U O:::::O     O:::::OO:::::O     O:::::O  D:::::D     D:::::DE:::::::::::::::E          "
    echo "Q:::::O     Q:::::Q U:::::D     D:::::U O:::::O     O:::::OO:::::O     O:::::O  D:::::D     D:::::DE::::::EEEEEEEEEE          "
    echo "Q:::::O  QQQQ:::::Q U:::::D     D:::::U O:::::O     O:::::OO:::::O     O:::::O  D:::::D     D:::::DE:::::E                    "
    echo "Q::::::O Q::::::::Q U::::::U   U::::::U O::::::O   O::::::OO::::::O   O::::::O  D:::::D    D:::::D E:::::E       EEEEEE        "
    echo "Q:::::::QQ::::::::Q U:::::::UUU:::::::U O:::::::OOO:::::::OO:::::::OOO:::::::ODDD:::::DDDDD:::::DEE::::::EEEEEEEE:::::E        "
    echo " QQ::::::::::::::Q   UU:::::::::::::UU   OO:::::::::::::OO  OO:::::::::::::OO D:::::::::::::::DD E::::::::::::::::::::E         "
    echo "   QQ:::::::::::Q      UU:::::::::UU       OO:::::::::OO      OO:::::::::OO   D::::::::::::DDD   E::::::::::::::::::::E         "
    echo "     QQQQQQQQ::::QQ      UUUUUUUUU           OOOOOOOOO          OOOOOOOOO     DDDDDDDDDDDDD      EEEEEEEEEEEEEEEEEEEEEE         "
    echo "             Q:::::Q                                                                                                             "
    echo "              QQQQQQ                                                                                                             "
    echo "                                                                                                                               "
    echo -e "${NC}"
}

# ============================================
#            Logging & Progress
# ============================================
log_message() {
    local type="$1"
    local message="$2"
    case "$type" in
        "info")    echo -e "${BLUE}[INFO]${NC} $message" ;;
        "success") echo -e "${GREEN}[SUCCESS]${NC} $message" ;;
        "warning") echo -e "${YELLOW}[WARNING]${NC} $message" ;;
        "error")   echo -e "${RED}[ERROR]${NC} $message" >&2 ;;
    esac
}

log_progress() {
    local message="$1"
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo -e "${BLUE}[${CURRENT_STEP}/${TOTAL_STEPS}]${NC} $message"
}

run_command() {
    local cmd="$1"
    eval "$cmd" >> "$LOG_FILE" 2>&1
    if [ $? -ne 0 ]; then
        log_message "error" "Command failed: $cmd. See $LOG_FILE for details."
        exit 1
    fi
}

# ============================================
#            Root Privilege Check
# ============================================
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        log_message "error" "Please run as root or use sudo."
        exit 1
    fi
}

INSTALL_USER="${SUDO_USER:-$USER}"

# ============================================
#    Enable or Disable Buttons & LEDs
# ============================================
configure_buttons_leds() {
    log_progress "Configuring Buttons and LEDs activation..."

    local MAIN_PY_PATH="/home/$INSTALL_USER/Quoode/src/main.py"
    CONFIGURE_BUTTONS_LEDS=false

    if [[ ! -f "$MAIN_PY_PATH" ]]; then
        log_message "error" "main.py not found at $MAIN_PY_PATH."
        exit 1
    fi

    while true; do
        read -rp "Do you need buttons and LEDs activated? (y/n): " yn
        case $yn in
            [Yy]* )
                CONFIGURE_BUTTONS_LEDS=true
                log_message "info" "Buttons and LEDs will be activated."
                if grep -q "^[#]*\s*buttons_leds\s*=\s*ButtonsLEDController" "$MAIN_PY_PATH"; then
                    sed -i.bak '/buttons_leds\s*=\s*ButtonsLEDController/ s/^#//' "$MAIN_PY_PATH"
                    log_message "success" "Activated 'buttons_leds = ButtonsLEDController(...)' in main.py."
                else
                    log_message "info" "'buttons_leds = ButtonsLEDController(...)' is already active."
                fi

                if grep -q "^[#]*\s*buttons_leds.start()" "$MAIN_PY_PATH"; then
                    sed -i.bak '/buttons_leds.start()/ s/^#//' "$MAIN_PY_PATH"
                    log_message "success" "Activated 'buttons_leds.start()' in main.py."
                else
                    log_message "info" "'buttons_leds.start()' is already active."
                fi
                break
                ;;
            [Nn]* )
                CONFIGURE_BUTTONS_LEDS=false
                log_message "info" "Buttons and LEDs will be deactivated."
                if grep -q "^[^#]*\s*buttons_leds\s*=\s*ButtonsLEDController" "$MAIN_PY_PATH"; then
                    sed -i.bak '/buttons_leds\s*=\s*ButtonsLEDController/ s/^\(\s*\)/\1#/' "$MAIN_PY_PATH"
                    log_message "success" "Deactivated 'buttons_leds = ButtonsLEDController(...)' in main.py."
                else
                    log_message "info" "'buttons_leds = ButtonsLEDController(...)' is already deactivated."
                fi

                if grep -q "^[^#]*\s*buttons_leds.start()" "$MAIN_PY_PATH"; then
                    sed -i.bak '/buttons_leds.start()/ s/^\(\s*\)/\1#/' "$MAIN_PY_PATH"
                    log_message "success" "Deactivated 'buttons_leds.start()' in main.py."
                else
                    log_message "info" "'buttons_leds.start()' is already deactivated."
                fi
                break
                ;;
            * )
                log_message "warning" "Please answer with 'y' or 'n'."
                ;;
        esac
    done
    log_message "success" "Buttons and LEDs configuration completed."
}

# ============================================
#   System-Level Dependencies
# ============================================
install_system_dependencies() {
    log_progress "Installing system-level dependencies..."

    run_command "apt-get update"
    run_command "apt-get install -y \
        python3 \
        python3-dev \
        python3-pip \
        libjpeg-dev \
        zlib1g-dev \
        libfreetype6-dev \
        i2c-tools \
        python3-smbus \
        libgirepository1.0-dev \
        pkg-config \
        libcairo2-dev \
        libffi-dev \
        build-essential \
        libxml2-dev \
        libxslt1-dev \
        libssl-dev \
        lsof \
        libfftw3-dev \
        libasound2-dev \
        libncursesw5-dev \
        libpulse-dev \
        libtool \
        automake \
        autoconf \
        gcc \
        make \
        git \
        libtiff6 \
        libtiff-tools \
        libtiff-dev"

    log_message "success" "System-level dependencies installed successfully."
}

# ============================================
#    Upgrade pip, setuptools, wheel
# ============================================
upgrade_pip_system_wide() {
    log_progress "Upgrading pip, setuptools, and wheel system-wide..."
    run_command "python3 -m pip install --upgrade pip setuptools wheel --break-system-packages"
    log_message "success" "pip, setuptools, and wheel upgraded successfully."
}

# ============================================
#  Install Python Dependencies System-Wide
# ============================================
install_python_dependencies() {
    log_progress "Installing Python dependencies system-wide..."

    run_command "python3 -m pip install --upgrade \
        --ignore-installed \
        --no-cache-dir \
        --break-system-packages \
        --verbose -r /home/$INSTALL_USER/Quoode/requirements.txt > /home/$INSTALL_USER/install_requirements.log 2>&1"

    log_message "success" "Python dependencies installed successfully system-wide."
}

# ============================================
#  Enable I2C & SPI in Firmware
# ============================================
enable_i2c_spi() {
    log_progress "Ensuring I2C and SPI are enabled in config..."

    CONFIG_FILE="/boot/firmware/config.txt"
    if [ ! -f "$CONFIG_FILE" ]; then
        log_message "error" "Cannot find $CONFIG_FILE"
        exit 1
    fi

    # Enable I2C
    if grep -q "^dtparam=i2c_arm=" "$CONFIG_FILE"; then
        sed -i 's/^dtparam=i2c_arm=.*/dtparam=i2c_arm=on/' "$CONFIG_FILE"
        log_message "info" "I2C parameter updated to 'dtparam=i2c_arm=on'."
    else
        echo "dtparam=i2c_arm=on" >> "$CONFIG_FILE"
        log_message "info" "I2C parameter added."
    fi

    # Enable SPI
    if grep -q "^dtparam=spi=" "$CONFIG_FILE"; then
        sed -i 's/^dtparam=spi=.*/dtparam=spi=on/' "$CONFIG_FILE"
        log_message "info" "SPI parameter updated to 'dtparam=spi=on'."
    else
        echo "dtparam=spi=on" >> "$CONFIG_FILE"
        log_message "info" "SPI parameter added."
    fi

    run_command "modprobe i2c-dev"
    run_command "modprobe spi-bcm2835"

    log_message "success" "I2C and SPI enabled and modules loaded."
}

# ============================================
#   Detect MCP23017 I2C Address
# ============================================
detect_i2c_address() {
    log_progress "Detecting MCP23017 I2C address..."

    local i2c_output
    i2c_output=$(/usr/sbin/i2cdetect -y 1)
    echo "$i2c_output" >> "$LOG_FILE"

    echo "$i2c_output"

    local address
    address=$(echo "$i2c_output" | grep -oE '\b(20|21|22|23|24|25|26|27)\b' | head -n 1)

    if [[ -z "$address" ]]; then
        log_message "warning" "MCP23017 not found. Check wiring."
    else
        log_message "success" "Detected MCP23017 at 0x$address."
        update_buttonsleds_address "$address"
    fi
}

update_buttonsleds_address() {
    local detected_address="$1"
    local BUTTONSLEDS_FILE="/home/$INSTALL_USER/Quoode/src/hardware/buttonsleds.py"

    if [[ -f "$BUTTONSLEDS_FILE" ]]; then
        if grep -q "mcp23017_address" "$BUTTONSLEDS_FILE"; then
            run_command "sed -i \"s/mcp23017_address = 0x[0-9a-fA-F]\\{2\\}/mcp23017_address = 0x$detected_address/\" \"$BUTTONSLEDS_FILE\""
            log_message "success" "MCP23017 address updated to 0x$detected_address."
        else
            run_command "echo \"mcp23017_address = 0x$detected_address\" >> \"$BUTTONSLEDS_FILE\""
            log_message "success" "MCP23017 address added to buttonsleds.py."
        fi
    else
        log_message "error" "buttonsleds.py not found at $BUTTONSLEDS_FILE."
        exit 1
    fi
}

# ============================================
#           Configure Samba
# ============================================
setup_samba() {
    log_progress "Configuring Samba for Quoode..."

    local SMB_CONF="/etc/samba/smb.conf"

    if [ ! -f "$SMB_CONF.bak" ]; then
        run_command "cp $SMB_CONF $SMB_CONF.bak"
        log_message "info" "Backup of smb.conf created."
    fi

    if ! grep -q "\[Quoode\]" "$SMB_CONF"; then
        echo -e "\n[Quoode]
   path = /home/$INSTALL_USER/Quoode
   writable = yes
   browseable = yes
   guest ok = yes
   force user = $INSTALL_USER
   create mask = 0775
   directory mask = 0775
   public = no" >> "$SMB_CONF"
        log_message "success" "Samba configuration for Quoode added."
    else
        log_message "info" "Samba configuration for Quoode already exists."
    fi

    log_progress "Enabling and starting Samba services..."
    run_command "systemctl enable smbd nmbd"
    run_command "systemctl restart smbd nmbd"

    run_command "chown -R $INSTALL_USER:$INSTALL_USER /home/$INSTALL_USER/Quoode"
    run_command "chmod -R 755 /home/$INSTALL_USER/Quoode"
    log_message "success" "Samba and directory permissions configured."
}

# ============================================
#    Copy mpd oled file
# ============================================

copy_mpd_oled_fifo_conf() {
    log_progress "Installing mpd_oled_fifo.conf..."

    local SOURCE_CONF="/home/$INSTALL_USER/Quoode/mpd_oled_fifo.conf"
    local DEST_CONF="/usr/local/etc/mpd_oled_fifo.conf"

    if [[ -f "$SOURCE_CONF" ]]; then
        run_command "mkdir -p /usr/local/etc"
        run_command "cp \"$SOURCE_CONF\" \"$DEST_CONF\""
        log_message "success" "Copied mpd_oled_fifo.conf to /usr/local/etc."
    else
        log_message "warning" "mpd_oled_fifo.conf not found at $SOURCE_CONF, skipping."
    fi
}


# ============================================
#    Check if CAVA Already Installed
# ============================================
check_cava_installed() {
    if command -v cava >/dev/null 2>&1; then
        log_message "info" "CAVA is already installed. Skipping."
        return 0
    else
        return 1
    fi
}

# ============================================
#   Install CAVA from Fork (theshepherdmatt)
# ============================================
install_cava_from_fork() {
    log_progress "Installing CAVA from fork..."

    local CAVA_REPO="https://github.com/theshepherdmatt/cava.git"
    local CAVA_INSTALL_DIR="/home/$INSTALL_USER/cava"

    if check_cava_installed; then
        return
    fi

    log_progress "Installing CAVA build dependencies..."
    run_command "apt-get install -y \
        libfftw3-dev \
        libasound2-dev \
        libncursesw5-dev \
        libpulse-dev \
        libtool \
        automake \
        autoconf \
        gcc \
        make \
        pkg-config \
        libiniparser-dev \
        git"

    if [[ ! -d "$CAVA_INSTALL_DIR" ]]; then
        run_command "git clone $CAVA_REPO $CAVA_INSTALL_DIR"
        log_message "success" "Cloned CAVA repository."
    else
        log_message "info" "CAVA repo already exists. Pulling latest changes..."
        run_command "cd $CAVA_INSTALL_DIR && git pull"
    fi

    log_progress "Building & installing CAVA..."
    run_command "cd $CAVA_INSTALL_DIR && ./autogen.sh"
    run_command "cd $CAVA_INSTALL_DIR && ./configure"
    run_command "cd $CAVA_INSTALL_DIR && make"
    run_command "cd $CAVA_INSTALL_DIR && make install"

    log_message "success" "CAVA installed successfully."
}

# ============================================
#   Setup CAVA Config
# ============================================
setup_cava_config() {
    log_progress "Setting up CAVA configuration..."

    local CONFIG_DIR="/home/$INSTALL_USER/.config/cava"
    local CONFIG_FILE="$CONFIG_DIR/config"
    local REPO_CONFIG_FILE="/home/$INSTALL_USER/cava/config/default_config"

    run_command "mkdir -p $CONFIG_DIR"

    if [[ ! -f "$CONFIG_FILE" ]]; then
        if [[ -f "$REPO_CONFIG_FILE" ]]; then
            log_message "info" "Copying default CAVA config."
            run_command "cp $REPO_CONFIG_FILE $CONFIG_FILE"
        else
            log_message "error" "Default CAVA config file not found in repo."
            exit 1
        fi
    else
        log_message "info" "CAVA config already exists. Skipping copy."
    fi

    run_command "chown -R $INSTALL_USER:$INSTALL_USER $CONFIG_DIR"
    log_message "success" "CAVA configuration setup complete."
}

# ============================================
#   Configure CAVA Service
# ============================================
setup_cava_service() {
    log_progress "Setting up the CAVA Service..."

    local CAVA_SERVICE_FILE="/etc/systemd/system/cava.service"
    local SRC_CAVA_FILE="/home/$INSTALL_USER/Quoode/service/cava.service"

    if [[ -f "$SRC_CAVA_FILE" ]]; then
        run_command "sed -i \"s:__INSTALL_USER__:$INSTALL_USER:g\" \"$SRC_CAVA_FILE\""
        run_command "cp \"$SRC_CAVA_FILE\" \"$CAVA_SERVICE_FILE\""
        log_message "success" "cava.service copied to /etc/systemd/system/."
    else
        log_message "error" "cava.service not found in /home/$INSTALL_USER/Quoode/service."
        exit 1
    fi

    run_command "systemctl daemon-reload"
    run_command "systemctl enable cava.service"
    run_command "systemctl start cava.service"

    log_message "success" "CAVA Service enabled and started."
}

# ============================================
#  Overwrite moOde's mpd.php (Optional)
# ============================================
overwrite_moode_mpdphp() {
    log_progress "Overwriting moOde's mpd.php with custom version..."
    local MOODE_MPD_PHP="/var/www/inc/mpd.php"
    local CUSTOM_MPD_PHP="/home/$INSTALL_USER/Quoode/moode_patches/mpd.php"   # Adjust the path if needed

    if [[ -f "$MOODE_MPD_PHP" ]]; then
        # Backup original
        run_command "cp $MOODE_MPD_PHP ${MOODE_MPD_PHP}.orig"
        log_message "info" "Backed up original mpd.php to mpd.php.orig"
    fi

    if [[ -f "$CUSTOM_MPD_PHP" ]]; then
        run_command "cp $CUSTOM_MPD_PHP $MOODE_MPD_PHP"
        log_message "success" "mpd.php overwritten with custom version."
        # Optionally, restart MPD
        run_command "systemctl restart mpd"
        log_message "info" "MPD restarted after mpd.php overwrite."
    else
        log_message "warning" "Custom mpd.php not found at $CUSTOM_MPD_PHP. Skipping."
    fi
}

# ============================================
#  Set Ownership & Permissions (Project Dir)
# ============================================
set_permissions() {
    log_progress "Setting ownership & permissions..."

    run_command "chown -R $INSTALL_USER:$INSTALL_USER /home/$INSTALL_USER/Quoode"
    run_command "chmod -R 755 /home/$INSTALL_USER/Quoode"

    log_message "success" "Ownership & permissions set for /home/$INSTALL_USER/Quoode."
}

# ============================================
#                MAIN Routine
# ============================================
main() {
    banner
    log_message "info" "Starting the installation script..."
    check_root

    configure_buttons_leds
    enable_i2c_spi

    if [ "$CONFIGURE_BUTTONS_LEDS" = true ]; then
        detect_i2c_address
    else
        log_message "info" "Skipping I2C address detection (buttons/LEDs not activated)."
    fi

    install_system_dependencies
    upgrade_pip_system_wide
    install_python_dependencies

    # Quoode Main Service
    log_progress "Setting up the Main Quoode Service..."
    local SERVICE_FILE="/etc/systemd/system/quoode.service"
    local SRC_SERVICE_FILE="/home/$INSTALL_USER/Quoode/service/quoode.service"
    if [[ -f "$SRC_SERVICE_FILE" ]]; then
        sed "s|__INSTALL_USER__|$INSTALL_USER|g" "$SRC_SERVICE_FILE" > "$SERVICE_FILE"
        log_message "success" "quoode.service configured for user $INSTALL_USER."
        run_command "systemctl daemon-reload"
        run_command "systemctl enable --now quoode.service"
        log_message "success" "Main Quoode Service enabled & started."
    else
        log_message "error" "quoode.service not found in /home/$INSTALL_USER/Quoode/service."
    fi

    configure_mpd
    install_cava_from_fork
    setup_cava_config
    setup_cava_service
    setup_samba
    set_permissions
    copy_mpd_oled_fifo_conf

    # (Optional) Overwrite moOde's mpd.php
    overwrite_moode_mpdphp

    log_message "success" "Installation complete. Review $LOG_FILE for details if needed."
}

# Execute main
main
