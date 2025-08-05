#!/bin/bash
set -e  # Exit immediately on a non-zero status (fail on error)
#set -x  # Uncomment for debugging (prints each command before execution)

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
TOTAL_STEPS=11
CURRENT_STEP=0
LOG_FILE="/home/${SUDO_USER:-$USER}/install.log"

# Remove any existing log file
rm -f "$LOG_FILE"

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
#   Dynamically update config.yaml user path
# ============================================
update_config_yaml_user_path() {
    log_progress "Dynamically updating config.yaml user path..."

    local CONFIG_TEMPLATE="/home/$INSTALL_USER/Quoode/config_template.yaml"
    local FINAL_CONFIG="/home/$INSTALL_USER/Quoode/config.yaml"

    if [[ ! -f "$CONFIG_TEMPLATE" ]]; then
        log_message "warning" "No config_template.yaml found, skipping dynamic user path substitution."
        return
    fi

    # We'll replace any occurrences of {USER} with the actual username:
    sed "s|{USER}|$INSTALL_USER|g" "$CONFIG_TEMPLATE" > "$FINAL_CONFIG"

    log_message "success" "Created config.yaml with user=$INSTALL_USER replaced in paths."
}

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

setup_python_venv_and_deps() {
    log_progress "Setting up Python venv and installing dependencies..."

    VENV_DIR="/home/$INSTALL_USER/Quoode/.venv"
    REQUIREMENTS_FILE="/home/$INSTALL_USER/Quoode/requirements.txt"

    # Install venv if not present
    run_command "apt-get install -y python3-venv python3-pip"

    # Create venv if missing
    if [ ! -d \"$VENV_DIR\" ]; then
        run_command "python3 -m venv $VENV_DIR"
    fi

    # Activate venv and install/upgrade pip/tools/deps
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip setuptools wheel
    pip install --upgrade --force-reinstall -r "$REQUIREMENTS_FILE"
    deactivate

    log_message "success" "Python venv and dependencies are set up in $VENV_DIR."
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
   public = yes" >> "$SMB_CONF"
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
    log_message "info" "Starting the installation script..."
    check_root

    update_config_yaml_user_path

    configure_buttons_leds
    enable_i2c_spi

    if [ "$CONFIGURE_BUTTONS_LEDS" = true ]; then
        detect_i2c_address
    else
        log_message "info" "Skipping I2C address detection (buttons/LEDs not activated)."
    fi

    install_system_dependencies
    setup_python_venv_and_deps

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

    # If you have an mpd configuration function, call it here
    # configure_mpd  # (commented or remove if you don't need it)

    setup_samba
    set_permissions
    
    log_message "success" "Installation complete. Review $LOG_FILE for details if needed."
}

# Execute main
main
