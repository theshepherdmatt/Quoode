#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status
#set -x  # Uncomment to enable debugging

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
TOTAL_STEPS=11  # Updated from 10 to 11
CURRENT_STEP=0
LOG_FILE="install.log"

# Remove existing log file
rm -f "$LOG_FILE"

# ============================
#   ASCII Art Banner Function
# ============================
banner() {
    echo -e "${MAGENTA}"
    echo "   ________  ___  ___  ________  ________  ___  ________ ___    ___   "
    echo "  |\   __  \|\  \|\  \|\   __  \|\   ___ \|\  \|\  _____\\  \  /  /|  "
    echo "  \ \  \|\  \ \  \\\  \ \  \|\  \ \  \_|\ \ \  \ \  \__/\ \  \/  / /  "
    echo "   \ \  \\\  \ \  \\\  \ \   __  \ \  \ \\ \ \  \ \   __\\ \    / /   "
    echo "    \ \  \\\  \ \  \\\  \ \  \ \  \ \  \_\\ \ \  \ \  \_| \/  /  /    "
    echo "     \ \_____  \ \_______\ \__\ \__\ \_______\ \__\ \__\__/  / /      "
    echo "      \|___| \__\|_______|\|__|\|__|\|_______|\|__|\|__|\___/ /       "
    echo "            \|__|                                      \|___|/        "
    echo -e "${NC}"
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
#   Install System-Level Dependencies
# ============================
install_system_dependencies() {
    log_progress "Installing system-level dependencies..."

    # Update package lists
    run_command "apt-get update"

    # Install essential packages
    run_command "apt-get install -y \
        python3.7 \
        python3.7-dev \
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
        lsof"

    log_message "success" "System-level dependencies installed successfully."
}

# ============================
#   Upgrade pip, setuptools, and wheel
# ============================
upgrade_pip() {
    log_progress "Upgrading pip, setuptools, and wheel..."

    run_command "python3.7 -m pip install --upgrade pip setuptools wheel"

    log_message "success" "pip, setuptools, and wheel upgraded."
}

# ============================
#   Install Python Dependencies
# ============================
install_python_dependencies() {
    log_progress "Installing Python dependencies..."

    # Install pycairo first to resolve PyGObject dependency
    run_command "python3.7 -m pip install --upgrade --ignore-installed pycairo"

    # Install dependencies from requirements.txt globally with --ignore-installed
    run_command "python3.7 -m pip install --upgrade --ignore-installed -r /home/volumio/Quadify/requirements.txt"

    log_message "success" "Python dependencies installed successfully."
}

# ============================
#   Enable I2C and SPI in config.txt
# ============================
enable_i2c_spi() {
    log_progress "Enabling I2C and SPI in config.txt..."

    CONFIG_FILE="/boot/userconfig.txt"

    if [ ! -f "$CONFIG_FILE" ]; then
        run_command "touch \"$CONFIG_FILE\""
    fi

    # Enable SPI and I2C
    if ! grep -q "^dtparam=spi=on" "$CONFIG_FILE"; then
        echo "dtparam=spi=on" >> "$CONFIG_FILE"
        log_message "success" "SPI enabled."
    else
        log_message "info" "SPI is already enabled."
    fi

    if ! grep -q "^dtparam=i2c_arm=on" "$CONFIG_FILE"; then
        echo "dtparam=i2c_arm=on" >> "$CONFIG_FILE"
        log_message "success" "I2C enabled."
    else
        log_message "info" "I2C is already enabled."
    fi

    log_message "success" "I2C and SPI enabled in config.txt."

    # Load kernel modules
    log_progress "Loading I2C and SPI kernel modules..."
    run_command "modprobe i2c-dev"
    run_command "modprobe spi-bcm2835"
    log_message "success" "I2C and SPI kernel modules loaded."

    # Verify that /dev/i2c-1 exists
    if [ -e /dev/i2c-1 ]; then
        log_message "success" "/dev/i2c-1 is present."
    else
        log_message "warning" "/dev/i2c-1 is not present. Attempting to initialize I2C..."
        run_command "modprobe i2c-bcm2708"
        sleep 1
        if [ -e /dev/i2c-1 ]; then
            log_message "success" "/dev/i2c-1 successfully initialized."
        else
            log_message "error" "/dev/i2c-1 could not be initialized. Please ensure I2C is enabled correctly."
            exit 1
        fi
    fi
}

# ============================
#   Detect MCP23017 I2C Address
# ============================

detect_i2c_address() {
    log_progress "Detecting MCP23017 I2C address..."

    # Use the absolute path to i2cdetect and capture the output
    i2c_output=$(/usr/sbin/i2cdetect -y 1)
    echo "$i2c_output" >> "$LOG_FILE"
    
    # For debugging: Print the i2c_output to the terminal
    echo "$i2c_output"

    # Use word boundaries in grep to match exact addresses
    address=$(echo "$i2c_output" | grep -oE '\b(20|21|22|23|24|25|26|27)\b' | head -n 1)

    if [[ -z "$address" ]]; then
        log_message "warning" "MCP23017 not found. Check wiring and connections as per instructions on our website."
    else
        log_message "success" "Detected MCP23017 at I2C address: 0x$address."
        update_buttonsleds_address "$address"
    fi
}

# ============================
#   Update MCP23017 Address in buttonsleds.py
# ============================
update_buttonsleds_address() {
    local detected_address="$1"
    BUTTONSLEDS_FILE="/home/volumio/Quadify/src/hardware/buttonsleds.py"

    if [[ -f "$BUTTONSLEDS_FILE" ]]; then
        # Check if the line exists
        if grep -q "mcp23017_address" "$BUTTONSLEDS_FILE"; then
            # Replace the existing address
            run_command "sed -i \"s/mcp23017_address = 0x[0-9a-fA-F]\\{2\\}/mcp23017_address = 0x$detected_address/\" \"$BUTTONSLEDS_FILE\""
            log_message "success" "Updated MCP23017 address in buttonsleds.py to 0x$detected_address."
        else
            # Append the address line if it doesn't exist
            run_command "echo \"mcp23017_address = 0x$detected_address\" >> \"$BUTTONSLEDS_FILE\""
            log_message "success" "Added MCP23017 address in buttonsleds.py as 0x$detected_address."
        fi
    else
        log_message "error" "buttonsleds.py not found at $BUTTONSLEDS_FILE. Ensure the path is correct."
        exit 1
    fi
}

# ============================
#   Configure Systemd Service
# ============================
setup_main_service() {
    log_progress "Setting up the Main Quadify Service..."

    SERVICE_FILE="/etc/systemd/system/quadify.service"

    # Copy the service file from the service folder
    if [[ -f "/home/volumio/Quadify/service/quadify.service" ]]; then
        run_command "cp /home/volumio/Quadify/service/quadify.service \"$SERVICE_FILE\""
        log_message "success" "quadify.service copied to $SERVICE_FILE."
    else
        log_message "error" "Service file quadify.service not found in services directory."
        exit 1
    fi

    # Reload systemd daemon to recognize the new service
    run_command "systemctl daemon-reload"

    # Enable and start the service
    run_command "systemctl enable quadify.service"
    run_command "systemctl start quadify.service"

    log_message "success" "Main Quadify Service has been enabled and started."
}

# ============================
#   Configure Buttons and LEDs
# ============================
configure_buttons_leds() {
    log_progress "Configuring Buttons and LEDs activation..."

    # Path to main.py
    MAIN_PY_PATH="/home/volumio/Quadify/src/main.py"

    # Check if main.py exists
    if [[ ! -f "$MAIN_PY_PATH" ]]; then
        log_message "error" "main.py not found at $MAIN_PY_PATH. Please ensure the path is correct."
        exit 1
    fi

    # Prompt the user
    while true; do
        read -rp "Do you need buttons and LEDs activated? (y/n): " yn
        case $yn in
            [Yy]* )
                log_message "info" "Buttons and LEDs will be activated."
                # Uncomment the initialization line
                if grep -q "^[#]*\s*buttons_leds\s*=\s*ButtonsLEDController" "$MAIN_PY_PATH"; then
                    sed -i.bak '/buttons_leds\s*=\s*ButtonsLEDController/ s/^#//' "$MAIN_PY_PATH"
                    log_message "success" "Activated 'buttons_leds = ButtonsLEDController(...)' in main.py."
                else
                    log_message "info" "'buttons_leds = ButtonsLEDController(...)' is already active in main.py."
                fi

                # Uncomment the start line
                if grep -q "^[#]*\s*buttons_leds.start()" "$MAIN_PY_PATH"; then
                    sed -i.bak '/buttons_leds.start()/ s/^#//' "$MAIN_PY_PATH"
                    log_message "success" "Activated 'buttons_leds.start()' in main.py."
                else
                    log_message "info" "'buttons_leds.start()' is already active in main.py."
                fi
                break
                ;;
            [Nn]* )
                log_message "info" "Buttons and LEDs will be deactivated."
                # Comment out the initialization line by adding a '#'
                if grep -q "^[^#]*\s*buttons_leds\s*=\s*ButtonsLEDController" "$MAIN_PY_PATH"; then
                    # Add '#' after leading spaces
                    sed -i.bak '/buttons_leds\s*=\s*ButtonsLEDController/ s/^\(\s*\)/\1#/' "$MAIN_PY_PATH"
                    log_message "success" "Deactivated 'buttons_leds = ButtonsLEDController(...)' in main.py."
                else
                    log_message "info" "'buttons_leds = ButtonsLEDController(...)' is already deactivated in main.py."
                fi

                # Comment out the start line by adding a '#'
                if grep -q "^[^#]*\s*buttons_leds.start()" "$MAIN_PY_PATH"; then
                    # Add '#' after leading spaces
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
#   Set Ownership and Permissions
# ============================
set_permissions() {
    log_progress "Setting ownership and permissions of project directory..."

    run_command "chown -R volumio:volumio /home/volumio/Quadify"
    run_command "chmod -R 755 /home/volumio/Quadify"

    log_message "success" "Ownership and permissions set to volumio user."
}

# ============================
#   Main Installation Function
# ============================
main() {
    banner
    log_message "info" "Starting the installation script..."
    check_root
    install_system_dependencies
    enable_i2c_spi
    upgrade_pip
    install_python_dependencies
    detect_i2c_address
    setup_main_service

    # Add the new configuration step here
    configure_buttons_leds

    set_permissions
    log_message "success" "Installation complete. Please verify the setup."
}

# Execute the main function
main
