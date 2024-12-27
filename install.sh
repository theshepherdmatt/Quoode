
#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status
# Uncomment the next line for debugging
# set -x

# ============================
#   Colour Code Definitions
# ============================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# ============================
#   Variables for Progress Tracking
# ============================
TOTAL_STEPS=17
CURRENT_STEP=0
LOG_FILE="/home/$INSTALL_USER/install.log"

# Remove existing log file
rm -f "$LOG_FILE"

# ============================
#   ASCII Art Banner Function
# ============================
banner() {
    echo -e "\033[0;35m"
    echo "                                                                                                                                 "
    echo "                                                                  dddddddd                                                       "
    echo "     QQQQQQQQQ     UUUUUUUU     UUUUUUUU     OOOOOOOOO          OOOOOOOOO     DDDDDDDDDDDDD      EEEEEEEEEEEEEEEEEEEEEE         "
    echo "   QQ:::::::::QQ   U::::::U     U::::::U   OO:::::::::OO      OO:::::::::OO   D::::::::::::DDD   E::::::::::::::::::::E         "
    echo " QQ:::::::::::::QQ U::::::U     U::::::U OO:::::::::::::OO  OO:::::::::::::OO D:::::::::::::::DD E::::::::::::::::::::E         "
    echo "Q:::::::QQQ:::::::QUU:::::U     U:::::UUO:::::::OOO:::::::OO:::::::OOO:::::::ODDD:::::DDDDD:::::DEE::::::EEEEEEEEE::::E         "
    echo "Q::::::O   Q::::::Q U:::::U     U:::::U O::::::O   O::::::OO::::::O   O::::::O  D:::::D    D:::::D E:::::E       EEEEEE         "
    echo "Q:::::O     Q:::::Q U:::::D     D:::::U O:::::O     O:::::OO:::::O     O:::::O  D:::::D     D:::::DE:::::E                     "
    echo "Q:::::O     Q:::::Q U:::::D     D:::::U O:::::O     O:::::OO:::::O     O:::::O  D:::::D     D:::::DE::::::EEEEEEEEEE           "
    echo "Q:::::O     Q:::::Q U:::::D     D:::::U O:::::O     O:::::OO:::::O     O:::::O  D:::::D     D:::::DE:::::::::::::::E           "
    echo "Q:::::O     Q:::::Q U:::::D     D:::::U O:::::O     O:::::OO:::::O     O:::::O  D:::::D     D:::::DE:::::::::::::::E           "
    echo "Q:::::O     Q:::::Q U:::::D     D:::::U O:::::O     O:::::OO:::::O     O:::::O  D:::::D     D:::::DE::::::EEEEEEEEEE           "
    echo "Q:::::O  QQQQ:::::Q U:::::D     D:::::U O:::::O     O:::::OO:::::O     O:::::O  D:::::D     D:::::DE:::::E                     "
    echo "Q::::::O Q::::::::Q U::::::U   U::::::U O::::::O   O::::::OO::::::O   O::::::O  D:::::D    D:::::D E:::::E       EEEEEE         "
    echo "Q:::::::QQ::::::::Q U:::::::UUU:::::::U O:::::::OOO:::::::OO:::::::OOO:::::::ODDD:::::DDDDD:::::DEE::::::EEEEEEEE:::::E         "
    echo " QQ::::::::::::::Q   UU:::::::::::::UU   OO:::::::::::::OO  OO:::::::::::::OO D:::::::::::::::DD E::::::::::::::::::::E         "
    echo "   QQ:::::::::::Q      UU:::::::::UU       OO:::::::::OO      OO:::::::::OO   D::::::::::::DDD   E::::::::::::::::::::E         "
    echo "     QQQQQQQQ::::QQ      UUUUUUUUU           OOOOOOOOO          OOOOOOOOO     DDDDDDDDDDDDD      EEEEEEEEEEEEEEEEEEEEEE         "
    echo "             Q:::::Q                                                                                                           "
    echo "              QQQQQQ                                                                                                           "
    echo "                                                                                                                               "
    echo "                                                                                                                                 "
    echo -e "\033[0m"
}


# ============================
#   Log Message Functions
# ============================
log_message() {
    local type="$1"
    local message="$2"
    case "$type" in
        "info") echo -e "${BLUE}[INFO]${NC} $message" ;;
        "success") echo -e "${GREEN}[SUCCESS]${NC} $message" ;;
        "warning") echo -e "${YELLOW}[WARNING]${NC} $message" ;;
        "error") echo -e "${RED}[ERROR]${NC} $message" >&2 ;;
    esac
}

log_progress() {
    local message="$1"
    CURRENT_STEP=$(( CURRENT_STEP + 1 ))
    echo -e "${BLUE}[${CURRENT_STEP}/${TOTAL_STEPS}]${NC} $message"
}

# ============================
#   Run Command Function
# ============================
run_command() {
    local cmd="$1"
    eval "$cmd" >> "$LOG_FILE" 2>&1
    if [ $? -ne 0 ]; then
        log_message "error" "Command failed: $cmd. See $LOG_FILE for details."
        exit 1
    fi
}

# ============================
#   Check for Root Privileges
# ============================
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        log_message "error" "Please run as root or use sudo."
        exit 1
    fi
}

# ============================
#   Detect Current (Non-Root) User
# ============================
INSTALL_USER="${SUDO_USER:-$USER}"

# ============================
#   Configure Buttons and LEDs Activation
# ============================
configure_buttons_leds() {
    log_progress "Configuring Buttons and LEDs activation..."

    MAIN_PY_PATH="/home/$INSTALL_USER/Quoode/src/main.py"
    CONFIGURE_BUTTONS_LEDS=false  # Initialize as false

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
                    log_message "info" "'buttons_leds = ButtonsLEDController(...)' is already active in main.py."
                fi

                if grep -q "^[#]*\s*buttons_leds.start()" "$MAIN_PY_PATH"; then
                    sed -i.bak '/buttons_leds.start()/ s/^#//' "$MAIN_PY_PATH"
                    log_message "success" "Activated 'buttons_leds.start()' in main.py."
                else
                    log_message "info" "'buttons_leds.start()' is already active in main.py."
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
                    log_message "info" "'buttons_leds = ButtonsLEDController(...)' is already deactivated in main.py."
                fi

                if grep -q "^[^#]*\s*buttons_leds.start()" "$MAIN_PY_PATH"; then
                    sed -i.bak '/buttons_leds.start()/ s/^\(\s*\)/\1#/' "$MAIN_PY_PATH"
                    log_message "success" "Deactivated 'buttons_leds.start()' in main.py."
                else
                    log_message "info" "'buttons_leds.start()' is already deactivated in main.py."
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


# ============================
#   Install System-Level Dependencies
# ============================
install_system_dependencies() {
    log_progress "Installing system-level dependencies, this might take a while....."

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
        git"

    log_message "success" "System-level dependencies installed successfully."
}

# ============================
#   Upgrade pip, setuptools, and wheel System-Wide
# ============================
upgrade_pip_system_wide() {
    log_progress "Upgrading pip, setuptools, and wheel system-wide..."

    run_command "python3 -m pip install --upgrade pip setuptools wheel --break-system-packages"

    log_message "success" "pip, setuptools, and wheel upgraded successfully system-wide."
}

# ============================
#   Install Python Dependencies System-Wide
# ============================
install_python_dependencies() {
    log_progress "Installing Python dependencies system-wide..."

    # Install dependencies from requirements.txt with verbose output and no cache
    run_command "python3 -m pip install --upgrade --ignore-installed --no-cache-dir --break-system-packages --verbose -r /home/$INSTALL_USER/Quoode/requirements.txt > /home/$INSTALL_USER/install_requirements.log 2>&1"

    # Check if the installation succeeded
    if [ $? -ne 0 ]; then
        log_message "error" "Python dependency installation failed. Check /home/$INSTALL_USER/install_requirements.log for details."
        exit 1
    fi

    log_message "success" "Python dependencies installed successfully system-wide."
}

# ============================
#   Enable I2C and SPI in firmware/config.txt
# ============================
enable_i2c_spi() {
    log_progress "Ensuring I2C and SPI are enabled in firmware/config.txt..."

    CONFIG_FILE="/boot/firmware/config.txt"

    # Ensure the file exists
    if [ ! -f "$CONFIG_FILE" ]; then
        log_message "error" "Configuration file $CONFIG_FILE does not exist."
        exit 1
    fi

    # Handle I2C
    if grep -q "^dtparam=i2c_arm=" "$CONFIG_FILE"; then
        if ! grep -q "^dtparam=i2c_arm=on" "$CONFIG_FILE"; then
            sed -i "s/^dtparam=i2c_arm=.*/dtparam=i2c_arm=on/" "$CONFIG_FILE"
            log_message "info" "Updated I2C configuration to 'dtparam=i2c_arm=on'."
        else
            log_message "info" "I2C is already enabled."
        fi
    else
        echo "dtparam=i2c_arm=on" >> "$CONFIG_FILE"
        log_message "success" "I2C configuration added to $CONFIG_FILE."
    fi

    # Handle SPI
    if grep -q "^dtparam=spi=" "$CONFIG_FILE"; then
        if ! grep -q "^dtparam=spi=on" "$CONFIG_FILE"; then
            sed -i "s/^dtparam=spi=.*/dtparam=spi=on/" "$CONFIG_FILE"
            log_message "info" "Updated SPI configuration to 'dtparam=spi=on'."
        else
            log_message "info" "SPI is already enabled."
        fi
    else
        echo "dtparam=spi=on" >> "$CONFIG_FILE"
        log_message "success" "SPI configuration added to $CONFIG_FILE."
    fi

    log_progress "Loading I2C and SPI kernel modules..."
    run_command "modprobe i2c-dev"
    run_command "modprobe spi-bcm2835"

    log_message "success" "I2C and SPI kernel modules loaded."
}

# ============================
#   Detect MCP23017 I2C Address
# ============================
detect_i2c_address() {
    log_progress "Detecting MCP23017 I2C address..."

    i2c_output=$(/usr/sbin/i2cdetect -y 1)
    echo "$i2c_output" >> "$LOG_FILE"

    echo "$i2c_output"

    address=$(echo "$i2c_output" | grep -oE '\b(20|21|22|23|24|25|26|27)\b' | head -n 1)

    if [[ -z "$address" ]]; then
        log_message "warning" "MCP23017 not found. Check wiring and connections as per instructions."
    else
        log_message "success" "Detected MCP23017 at I2C address: 0x$address."
        update_buttonsleds_address "$address"
    fi
}

update_buttonsleds_address() {
    local detected_address="$1"
    BUTTONSLEDS_FILE="/home/$INSTALL_USER/Quoode/src/hardware/buttonsleds.py"

    if [[ -f "$BUTTONSLEDS_FILE" ]]; then
        if grep -q "mcp23017_address" "$BUTTONSLEDS_FILE"; then
            run_command "sed -i \"s/mcp23017_address = 0x[0-9a-fA-F]\\{2\\}/mcp23017_address = 0x$detected_address/\" \"$BUTTONSLEDS_FILE\""
            log_message "success" "Updated MCP23017 address in buttonsleds.py to 0x$detected_address."
        else
            run_command "echo \"mcp23017_address = 0x$detected_address\" >> \"$BUTTONSLEDS_FILE\""
            log_message "success" "Added MCP23017 address in buttonsleds.py as 0x$detected_address."
        fi
    else
        log_message "error" "buttonsleds.py not found at $BUTTONSLEDS_FILE."
        exit 1
    fi
}

# ============================
#   Configure Samba
# ============================
setup_samba() {
    log_progress "Configuring Samba for Quoode..."

    SMB_CONF="/etc/samba/smb.conf"

    if [ ! -f "$SMB_CONF.bak" ]; then
        run_command "cp $SMB_CONF $SMB_CONF.bak"
        log_message "info" "Backup of smb.conf created."
    fi

    if ! grep -q "\[Quoode\]" "$SMB_CONF"; then
        echo -e "\n[Quoode]\n   path = /home/$INSTALL_USER/Quoode\n   writable = yes\n   browseable = yes\n   guest ok = yes\n   force user = $INSTALL_USER\n   create mask = 0775\n   directory mask = 0775\n   public = no" >> "$SMB_CONF"
        log_message "success" "Samba configuration for Quoode added."
    else
        log_message "info" "Samba configuration for Quoode already exists."
    fi

    run_command "systemctl restart smbd"
    log_message "success" "Samba service restarted."

    run_command "chown -R $INSTALL_USER:$INSTALL_USER /home/$INSTALL_USER/Quoode"
    run_command "chmod -R 755 /home/$INSTALL_USER/Quoode"
    log_message "success" "Permissions for /home/$INSTALL_USER/Quoode set successfully."
}

# ============================
#   Configure Systemd Service
# ============================
setup_main_service() {
    log_progress "Setting up the Main Quoode Service..."

    # Define service file paths
    SERVICE_FILE="/etc/systemd/system/quoode.service"
    SRC_SERVICE_FILE="/home/$INSTALL_USER/Quoode/service/quoode.service"

    # Check if source service file exists
    if [[ -f "$SRC_SERVICE_FILE" ]]; then
        # Replace the placeholder `__INSTALL_USER__` with the actual username
        sed "s|__INSTALL_USER__|$INSTALL_USER|g" "$SRC_SERVICE_FILE" > "$SERVICE_FILE"
        log_message "success" "Service file updated with user $INSTALL_USER and copied to $SERVICE_FILE."

        # Reload systemd and start the service
        run_command "systemctl daemon-reload"
        run_command "systemctl enable --now quoode.service" 
        log_message "success" "Main Quoode Service has been enabled and started."
    else
        log_message "error" "Service file quoode.service not found in /home/$INSTALL_USER/Quoode/service."
        exit 1
    fi
}

# ============================
#   Update MPD Configuration
# ============================
configure_mpd() {
    log_progress "Configuring MPD for CAVA in moOde..."

    MPD_OVERRIDE_FILE="/etc/mpd.conf"
    FIFO_OUTPUT="
    audio_output {
        type            \"fifo\"
        name            \"my_fifo\"
        path            \"/tmp/cava.fifo\"
        format          \"44100:16:2\"
    }"

    if [ ! -f "$MPD_OVERRIDE_FILE" ]; then
        log_progress "Creating MPD configuration file..."
        run_command "touch $MPD_OVERRIDE_FILE"
    fi

    if grep -q "path.*\"/tmp/cava.fifo\"" "$MPD_OVERRIDE_FILE"; then
        log_message "info" "FIFO output configuration already exists in MPD config."
    else
        log_progress "Adding FIFO output configuration to MPD config..."
        echo "$FIFO_OUTPUT" | tee -a "$MPD_OVERRIDE_FILE" >> "$LOG_FILE"
        log_message "success" "FIFO output configuration added to MPD config."
    fi

    log_progress "Restarting MPD to apply changes..."
    if systemctl restart mpd >> "$LOG_FILE" 2>&1; then
        log_message "success" "MPD restarted with updated configuration."
    else
        log_message "error" "Failed to restart MPD. Check the configuration and try again."
    fi
}

# ============================
#   Install CAVA Dependencies and Build
# ============================
check_cava_installed() {
    if command -v cava >/dev/null 2>&1; then
        log_message "info" "CAVA is already installed. Skipping installation."
        return 0
    else
        return 1
    fi
}

install_cava_from_fork() {
    log_progress "Installing CAVA from fork..."

    CAVA_REPO="https://github.com/theshepherdmatt/cava.git"
    CAVA_INSTALL_DIR="/home/$INSTALL_USER/cava"

    if check_cava_installed; then
        log_message "info" "Skipping CAVA installation."
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
        log_message "success" "Cloned CAVA repository from fork."
    else
        log_message "info" "CAVA repository already exists. Pulling latest changes..."
        run_command "cd $CAVA_INSTALL_DIR && git pull"
    fi

    log_progress "Building and installing CAVA..."
    run_command "cd $CAVA_INSTALL_DIR && ./autogen.sh"
    log_message "info" "autogen.sh completed"
    run_command "cd $CAVA_INSTALL_DIR && ./configure"
    log_message "info" "configure completed"
    run_command "cd $CAVA_INSTALL_DIR && make"
    log_message "info" "make completed"
    run_command "cd $CAVA_INSTALL_DIR && make install"
    log_message "success" "CAVA installed successfully."
}

# ============================
#   Install CAVA Configuration
# ============================
setup_cava_config() {
    log_progress "Setting up CAVA configuration..."

    CONFIG_DIR="/home/$INSTALL_USER/.config/cava"
    CONFIG_FILE="$CONFIG_DIR/config"
    REPO_CONFIG_FILE="/home/$INSTALL_USER/cava/config/default_config"

    run_command "mkdir -p $CONFIG_DIR"

    if [[ ! -f $CONFIG_FILE ]]; then
        if [[ -f $REPO_CONFIG_FILE ]]; then
            log_message "info" "Copying default CAVA configuration from repository."
            run_command "cp $REPO_CONFIG_FILE $CONFIG_FILE"
        else
            log_message "error" "Default configuration file not found in repository."
            exit 1
        fi
    else
        log_message "info" "CAVA configuration already exists. Skipping copy."
    fi

    run_command "chown -R $INSTALL_USER:$INSTALL_USER $CONFIG_DIR"
    log_message "success" "CAVA configuration setup completed."
}

# ============================
#   Configure CAVA Service
# ============================
setup_cava_service() {
    log_progress "Setting up the CAVA Service..."

    CAVA_SERVICE_FILE="/etc/systemd/system/cava.service"
    SRC_CAVA_FILE="/home/$INSTALL_USER/Quoode/service/cava.service"

    if [[ -f "$SRC_CAVA_FILE" ]]; then
        # Replace all occurrences of "__INSTALL_USER__" in the service file
        run_command "sed -i \"s:__INSTALL_USER__:$INSTALL_USER:g\" \"$SRC_CAVA_FILE\""

        # Copy the updated service file to the systemd directory
        run_command "cp \"$SRC_CAVA_FILE\" \"$CAVA_SERVICE_FILE\""
        log_message "success" "cava.service copied to $CAVA_SERVICE_FILE."
    else
        log_message "error" "Service file cava.service not found in /home/$INSTALL_USER/Quoode/service."
        exit 1
    fi

    # Reload systemd to recognize the new service file
    run_command "systemctl daemon-reload"
    run_command "systemctl enable cava.service"
    run_command "systemctl start cava.service"

    log_message "success" "CAVA Service has been enabled and started."
}

# ============================
#   Configure Samba
# ============================
setup_samba() {
    log_progress "Configuring Samba for Quoode..."

    SMB_CONF="/etc/samba/smb.conf"

    if [ ! -f "$SMB_CONF.bak" ]; then
        run_command "cp $SMB_CONF $SMB_CONF.bak"
        log_message "info" "Backup of smb.conf created."
    fi

    if ! grep -q "\[Quoode\]" "$SMB_CONF"; then
        echo -e "\n[Quoode]\n   path = /home/$INSTALL_USER/Quoode\n   writable = yes\n   browseable = yes\n   guest ok = yes\n   force user = $INSTALL_USER\n   create mask = 0775\n   directory mask = 0775\n   public = no" >> "$SMB_CONF"
        log_message "success" "Samba configuration for Quoode added."
    else
        log_message "info" "Samba configuration for Quoode already exists."
    fi

    run_command "systemctl restart smbd"
    log_message "success" "Samba service restarted."

    run_command "chown -R $INSTALL_USER:$INSTALL_USER /home/$INSTALL_USER/Quoode"
    run_command "chmod -R 755 /home/$INSTALL_USER/Quoode"
    log_message "success" "Permissions for /home/$INSTALL_USER/Quoode set successfully."
}

# ============================
#   Set Ownership and Permissions
# ============================
set_permissions() {
    log_progress "Setting ownership and permissions of project directory..."

    run_command "chown -R $INSTALL_USER:$INSTALL_USER /home/$INSTALL_USER/Quoode"
    run_command "chmod -R 755 /home/$INSTALL_USER/Quoode"

    log_message "success" "Ownership and permissions set for /home/$INSTALL_USER/Quoode."
}

# ============================
#   Main Installation Function
# ============================
main() {
    banner
    log_message "info" "Starting the installation script..."
    check_root
    configure_buttons_leds

    # Skip detect_i2c_address if buttons and LEDs are not configured
    if [ "$CONFIGURE_BUTTONS_LEDS" = true ]; then
        enable_i2c_spi
        detect_i2c_address
    else
        log_message "info" "Skipping I2C address detection as buttons and LEDs are not being used."
    fi

    install_system_dependencies
    upgrade_pip_system_wide
    install_python_dependencies
    setup_main_service

    configure_mpd
    echo "DEBUG: Finished installing MPD"

    install_cava_from_fork
    echo "DEBUG: Finished installing CAVA from fork"

    setup_cava_config
    echo "DEBUG: Finished installing CAVA Configuration"

    setup_cava_service
    echo "DEBUG: Finished installing CAVA Service"

    setup_samba

    set_permissions

    log_message "success" "Installation complete. Please verify the setup."
}

# Execute the main function
main
