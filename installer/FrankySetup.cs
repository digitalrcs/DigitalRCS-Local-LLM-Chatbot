// SPDX-License-Identifier: MIT
// Native Windows setup UI. Compile with the .NET Framework 4.x C# compiler.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Media;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

namespace DigitalRCS.Franky
{
    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            bool smoke = Array.IndexOf(args, "--smoke-test") >= 0;
            bool start = Array.IndexOf(args, "--start") >= 0;
            try
            {
                using (SetupForm form = new SetupForm(start, smoke))
                {
                    if (smoke)
                    {
                        // Construct and lay out the native controls without invoking a worker.
                        IntPtr handle = form.Handle;
                        form.PerformLayout();
                        return handle == IntPtr.Zero ? 1 : 0;
                    }
                    Application.Run(form);
                }
                return 0;
            }
            catch
            {
                if (!smoke) MessageBox.Show("Franky's setup window could not open. Try starting it again from the Start menu.",
                    "Franky setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            }
        }
    }

    internal sealed class ProviderChoice
    {
        public string Id;
        public string Name;
        public ProviderChoice(string id, string name) { Id = id; Name = name; }
        public override string ToString() { return Name; }
    }

    internal sealed class PortChoice
    {
        public string Port;
        public string Description;
        public override string ToString() { return Port + (Description.Length == 0 ? "" : " — " + Description); }
    }

    internal sealed class WorkerProgress
    {
        public string Message;
        public int Percent = -1;
    }

    internal sealed class WorkerResult
    {
        public bool Ok;
        public Dictionary<string, object> Data = new Dictionary<string, object>();
        public string Error = "The setup task did not finish. Please try again.";
    }

    internal sealed class SetupForm : Form
    {
        private readonly Color green = Color.FromArgb(40, 94, 69);
        private readonly Color ink = Color.FromArgb(26, 53, 42);
        private readonly Color paper = Color.FromArgb(247, 246, 239);
        private readonly Color muted = Color.FromArgb(83, 99, 89);
        private readonly string root;
        private readonly bool startOnOpen;
        private readonly bool smokeTest;
        private readonly List<TableLayoutPanel> pages = new List<TableLayoutPanel>();
        private readonly List<Button> actionButtons = new List<Button>();
        private readonly List<Control> inputControls = new List<Control>();
        private readonly Dictionary<string, string> addressLabels = new Dictionary<string, string>();
        private readonly ListBox navigation = new ListBox();
        private readonly Panel pageHost = new Panel();
        private readonly Label status = new Label();
        private readonly ProgressBar progress = new ProgressBar();
        private readonly Button back = new Button();
        private readonly Button next = new Button();
        private readonly ComboBox provider = new ComboBox();
        private readonly TextBox providerUrl = new TextBox();
        private readonly TextBox apiKey = new TextBox();
        private readonly CheckBox advancedLocal = new CheckBox();
        private readonly CheckBox onlineConsent = new CheckBox();
        private readonly ComboBox model = new ComboBox();
        private readonly Label providerHelp = new Label();
        private readonly Label keyHelp = new Label();
        private readonly Label answerState = new Label();
        private readonly Label voiceState = new Label();
        private readonly Label addressState = new Label();
        private readonly Label adapterHelp = new Label();
        private readonly Label robotState = new Label();
        private readonly Label readyState = new Label();
        private readonly Label readyDetails = new Label();
        private readonly Label doneState = new Label();
        private readonly Label doneDetails = new Label();
        private readonly ComboBox address = new ComboBox();
        private readonly ComboBox ports = new ComboBox();
        private readonly CheckBox boardConfirmed = new CheckBox();
        private FlowLayoutPanel lmStudioButtons;
        private TableLayoutPanel providerUrlFields;
        private TableLayoutPanel providerKeyFields;
        private Button saveProviderButton;
        private Button modelButton;
        private Button previewButton;
        private Button flashButton;
        private bool busy;
        private bool initialising;
        private bool providerSaved;
        private bool voicePrepared;
        private bool addressSaved;
        private bool bridgeReady;
        private bool keyConfigured;
        private string savedProvider = "lmstudio";
        private string bridgeUrl = "http://127.0.0.1:8766/";
        private SoundPlayer player;

        public SetupForm(bool start, bool smoke)
        {
            startOnOpen = start;
            smokeTest = smoke;
            string executableFolder = AppDomain.CurrentDomain.BaseDirectory;
            root = File.Exists(Path.Combine(executableFolder, "installer", "worker.py"))
                ? executableFolder : (File.Exists(Path.Combine(executableFolder, "worker.py"))
                    ? Directory.GetParent(executableFolder.TrimEnd(Path.DirectorySeparatorChar)).FullName : executableFolder);
            Text = "Franky setup — DigitalRCS";
            Font = new Font("Segoe UI", 10.5f, FontStyle.Regular, GraphicsUnit.Point);
            ForeColor = ink;
            BackColor = paper;
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(960, 720);
            MinimumSize = new Size(820, 620);
            AutoScaleMode = AutoScaleMode.Dpi;
            BuildShell();
            BuildWelcome();
            BuildAnswers();
            BuildVoice();
            BuildConnect();
            BuildRobot();
            BuildTryIt();
            BuildDone();
            navigation.SelectedIndex = 0;
            UpdateState();
            FormClosing += OnClosing;
            Shown += OnShown;
        }

        private void BuildShell()
        {
            TableLayoutPanel shell = new TableLayoutPanel();
            shell.Dock = DockStyle.Fill;
            shell.ColumnCount = 2;
            shell.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 188));
            shell.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            shell.RowCount = 3;
            shell.RowStyles.Add(new RowStyle(SizeType.Absolute, 100));
            shell.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            shell.RowStyles.Add(new RowStyle(SizeType.Absolute, 120));
            Controls.Add(shell);
            Panel header = new Panel();
            header.Dock = DockStyle.Fill;
            header.BackColor = green;
            header.Margin = Padding.Empty;
            Label title = new Label();
            title.Text = "Hello, I'm Franky.";
            title.Font = new Font("Segoe UI", 23, FontStyle.Bold);
            title.ForeColor = Color.White;
            title.AutoSize = true;
            title.Location = new Point(24, 12);
            header.Controls.Add(title);
            Label subtitle = new Label();
            subtitle.Text = "Your little frog companion · Windows setup";
            subtitle.ForeColor = Color.FromArgb(222, 237, 222);
            subtitle.AutoSize = true;
            subtitle.Location = new Point(26, 62);
            header.Controls.Add(subtitle);
            shell.Controls.Add(header, 0, 0);
            shell.SetColumnSpan(header, 2);
            navigation.Dock = DockStyle.Fill;
            navigation.BorderStyle = BorderStyle.None;
            navigation.BackColor = Color.FromArgb(232, 238, 225);
            navigation.ForeColor = ink;
            navigation.DrawMode = DrawMode.OwnerDrawFixed;
            navigation.ItemHeight = 48;
            navigation.Margin = Padding.Empty;
            navigation.AccessibleName = "Setup steps";
            navigation.Items.AddRange(new object[] { "Welcome", "Answers", "Voice", "Connect", "Robot", "Try it", "Everyday use" });
            navigation.DrawItem += delegate(object sender, DrawItemEventArgs e)
            {
                if (e.Index < 0) return;
                bool selected = (e.State & DrawItemState.Selected) != 0;
                using (Brush background = new SolidBrush(selected ? green : navigation.BackColor)) e.Graphics.FillRectangle(background, e.Bounds);
                TextRenderer.DrawText(e.Graphics, (e.Index + 1).ToString() + "   " + navigation.Items[e.Index], Font,
                    new Rectangle(e.Bounds.X + 14, e.Bounds.Y, e.Bounds.Width - 18, e.Bounds.Height),
                    selected ? Color.White : ink, TextFormatFlags.Left | TextFormatFlags.VerticalCenter);
                e.DrawFocusRectangle();
            };
            navigation.SelectedIndexChanged += delegate { ShowPage(navigation.SelectedIndex); };
            shell.Controls.Add(navigation, 0, 1);
            pageHost.Dock = DockStyle.Fill;
            pageHost.AutoScroll = true;
            pageHost.Margin = Padding.Empty;
            pageHost.Resize += delegate { WrapLabels(); };
            shell.Controls.Add(pageHost, 1, 1);

            TableLayoutPanel footer = new TableLayoutPanel();
            footer.Dock = DockStyle.Fill;
            footer.Padding = new Padding(18, 9, 18, 8);
            footer.BackColor = Color.White;
            footer.ColumnCount = 2;
            footer.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            footer.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 220));
            footer.RowCount = 2;
            footer.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            footer.RowStyles.Add(new RowStyle(SizeType.Absolute, 18));
            status.Text = "Welcome. Work through the steps at your own pace.";
            status.Dock = DockStyle.Fill;
            status.TextAlign = ContentAlignment.MiddleLeft;
            footer.Controls.Add(status, 0, 0);
            FlowLayoutPanel navButtons = new FlowLayoutPanel();
            navButtons.Dock = DockStyle.Fill;
            navButtons.FlowDirection = FlowDirection.RightToLeft;
            navButtons.WrapContents = false;
            navButtons.Padding = new Padding(0, 13, 0, 0);
            StyleButton(next, "&Next");
            StyleButton(back, "&Back");
            next.Click += delegate { if (!busy && navigation.SelectedIndex < pages.Count - 1) navigation.SelectedIndex++; };
            back.Click += delegate { if (!busy && navigation.SelectedIndex > 0) navigation.SelectedIndex--; };
            navButtons.Controls.Add(next);
            navButtons.Controls.Add(back);
            footer.Controls.Add(navButtons, 1, 0);
            progress.Dock = DockStyle.Fill;
            progress.Style = ProgressBarStyle.Continuous;
            footer.Controls.Add(progress, 0, 1);
            footer.SetColumnSpan(progress, 2);
            shell.Controls.Add(footer, 0, 2);
            shell.SetColumnSpan(footer, 2);
        }

        private TableLayoutPanel Page(string title, string intro)
        {
            TableLayoutPanel page = new TableLayoutPanel();
            page.ColumnCount = 1;
            page.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            page.AutoSize = true;
            page.AutoSizeMode = AutoSizeMode.GrowAndShrink;
            page.Dock = DockStyle.Top;
            page.Padding = new Padding(26, 22, 26, 28);
            page.Margin = Padding.Empty;
            pages.Add(page);
            Label heading = AddText(page, title);
            heading.Font = new Font("Segoe UI", 21, FontStyle.Bold);
            heading.Margin = new Padding(0, 0, 0, 12);
            AddText(page, intro);
            return page;
        }

        private Label AddText(TableLayoutPanel page, string text)
        {
            Label label = new Label();
            label.Text = text;
            ConfigureLabel(label);
            page.Controls.Add(label);
            return label;
        }

        private void ConfigureLabel(Label label)
        {
            label.AutoSize = true;
            label.Dock = DockStyle.Fill;
            label.MaximumSize = new Size(660, 0);
            label.Margin = new Padding(0, 0, 0, 12);
            label.Tag = "wrap";
        }

        private void AddState(TableLayoutPanel page, Label label, string text)
        {
            ConfigureLabel(label);
            label.Text = text;
            label.ForeColor = green;
            label.Font = new Font(Font, FontStyle.Bold);
            page.Controls.Add(label);
        }

        private void AddField(TableLayoutPanel page, string caption, Control control)
        {
            Label label = AddText(page, caption);
            label.Font = new Font(Font, FontStyle.Bold);
            label.Margin = new Padding(0, 5, 0, 4);
            control.Dock = DockStyle.Fill;
            control.Margin = new Padding(0, 0, 0, 12);
            control.AccessibleName = caption.Replace("&", "");
            page.Controls.Add(control);
            inputControls.Add(control);
        }

        private FlowLayoutPanel ButtonRow(TableLayoutPanel page)
        {
            FlowLayoutPanel row = new FlowLayoutPanel();
            row.Dock = DockStyle.Fill;
            row.AutoSize = true;
            row.WrapContents = true;
            row.Margin = new Padding(0, 2, 0, 12);
            page.Controls.Add(row);
            return row;
        }

        private TableLayoutPanel FieldGroup(TableLayoutPanel page)
        {
            TableLayoutPanel group = new TableLayoutPanel();
            group.ColumnCount = 1;
            group.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            group.AutoSize = true;
            group.Dock = DockStyle.Fill;
            group.Margin = Padding.Empty;
            page.Controls.Add(group);
            return group;
        }

        private void StyleButton(Button button, string text)
        {
            button.Text = text;
            button.AutoSize = true;
            button.MinimumSize = new Size(94, 37);
            button.Padding = new Padding(10, 3, 10, 3);
            button.Margin = new Padding(0, 0, 8, 7);
            button.BackColor = green;
            button.ForeColor = Color.White;
            button.FlatStyle = FlatStyle.Flat;
            button.FlatAppearance.BorderSize = 0;
            button.UseVisualStyleBackColor = false;
        }

        private Button Action(FlowLayoutPanel row, string text, Func<Task> action)
        {
            Button button = new Button();
            StyleButton(button, text);
            button.Click += async delegate
            {
                if (busy) return;
                try { await action(); }
                catch { Explain("Windows could not complete that action. Please try again."); }
            };
            row.Controls.Add(button);
            actionButtons.Add(button);
            return button;
        }

        private Button Link(FlowLayoutPanel row, string text, string url)
        {
            return Action(row, text, delegate { OpenUrl(url); return Task.FromResult(0); });
        }

        private void BuildWelcome()
        {
            TableLayoutPanel page = Page("Let's get acquainted", "Seven short steps connect Franky to this Windows PC or AI server. You can revisit any step later.");
            AddText(page, "Already included\r\nPython, the voice bridge, speech tools, and Franky's speech models are bundled with this installer. You do not need a Hugging Face account.");
            AddText(page, "Choose how Franky answers\r\nLM Studio keeps conversation processing on your PC or home network. Online providers are optional and require their own account or API key.");
            AddText(page, "Allow some time\r\nLM Studio and its chat models are separate downloads. Large models can take a while to download and load. Keep this window open while a task is running.");
            AddText(page, "Keep handy\r\nYour home 2.4 GHz Wi-Fi details and, only if the robot needs new firmware, a USB data cable for the LAFVIN LA064 ESP32-S3 N16R8 kit.");
            Action(ButtonRow(page), "Check this installation", Inspect);
        }

        private void BuildAnswers()
        {
            TableLayoutPanel page = Page("Where should answers come from?", "LM Studio keeps answers on your PC. Online services are optional.");
            provider.DropDownStyle = ComboBoxStyle.DropDownList;
            provider.Items.Add(new ProviderChoice("lmstudio", "LM Studio — local PC or home network"));
            provider.Items.Add(new ProviderChoice("openrouter", "OpenRouter — supported free models"));
            provider.Items.Add(new ProviderChoice("gemini", "Google Gemini — check account limits"));
            provider.Items.Add(new ProviderChoice("openai", "OpenAI API — metered usage"));
            provider.SelectedIndex = 0;
            AddField(page, "Answer provider", provider);
            ConfigureLabel(providerHelp);
            providerHelp.ForeColor = muted;
            page.Controls.Add(providerHelp);
            lmStudioButtons = ButtonRow(page);
            Action(lmStudioButtons, "Install LM Studio", async delegate { await RunAction("install_lmstudio", null, "Preparing LM Studio…"); });
            Action(lmStudioButtons, "Start LM Studio", async delegate { await RunAction("start_lmstudio", null, "Opening LM Studio…"); });
            Link(lmStudioButtons, "Official download", "https://lmstudio.ai/download");
            advancedLocal.Text = "LM Studio is on another PC or needs a token";
            advancedLocal.AutoSize = true;
            advancedLocal.Dock = DockStyle.Fill;
            advancedLocal.Margin = new Padding(0, 0, 0, 10);
            page.Controls.Add(advancedLocal);
            inputControls.Add(advancedLocal);
            advancedLocal.CheckedChanged += delegate { UpdateState(); WrapLabels(); };
            providerUrlFields = FieldGroup(page);
            providerUrl.Text = "http://127.0.0.1:1234/v1";
            AddField(providerUrlFields, "LM Studio API address", providerUrl);
            providerKeyFields = FieldGroup(page);
            apiKey.UseSystemPasswordChar = true;
            AddField(providerKeyFields, "API key (leave blank to keep an existing saved key)", apiKey);
            ConfigureLabel(keyHelp);
            keyHelp.ForeColor = muted;
            providerKeyFields.Controls.Add(keyHelp);
            onlineConsent.Text = "I agree to send conversation text to this provider and accept its usage limits and any charges.";
            onlineConsent.AutoSize = true;
            onlineConsent.MaximumSize = new Size(660, 0);
            onlineConsent.Dock = DockStyle.Fill;
            onlineConsent.Margin = new Padding(0, 0, 0, 12);
            page.Controls.Add(onlineConsent);
            inputControls.Add(onlineConsent);
            model.DropDownStyle = ComboBoxStyle.DropDownList;
            model.DropDownWidth = 620;
            Label modelLabel = AddText(page, "Chat model");
            modelLabel.Font = new Font(Font, FontStyle.Bold);
            modelLabel.Margin = new Padding(0, 3, 0, 4);
            TableLayoutPanel modelRow = new TableLayoutPanel();
            modelRow.ColumnCount = 2;
            modelRow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            modelRow.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            modelRow.AutoSize = true;
            modelRow.Dock = DockStyle.Fill;
            modelRow.Margin = new Padding(0, 0, 0, 9);
            model.Dock = DockStyle.Fill;
            model.Margin = new Padding(0, 5, 10, 0);
            model.AccessibleName = "Chat model";
            modelRow.Controls.Add(model, 0, 0);
            inputControls.Add(model);
            FlowLayoutPanel findModels = new FlowLayoutPanel();
            findModels.AutoSize = true;
            findModels.WrapContents = false;
            findModels.Dock = DockStyle.Fill;
            findModels.Margin = Padding.Empty;
            modelButton = Action(findModels, "Find models", LoadModels);
            modelButton.Margin = Padding.Empty;
            modelRow.Controls.Add(findModels, 1, 0);
            page.Controls.Add(modelRow);
            saveProviderButton = Action(ButtonRow(page), "Save answer settings", SaveProvider);
            AddState(page, answerState, "Choose a provider and model, then save.");
            provider.SelectedIndexChanged += delegate
            {
                if (initialising) return;
                apiKey.Clear(); onlineConsent.Checked = false; model.Items.Clear(); providerSaved = false; bridgeReady = false;
                string id = ProviderId();
                providerUrl.Text = id == "lmstudio" ? "http://127.0.0.1:1234/v1" : id == "openrouter" ? "https://openrouter.ai/api/v1" : id == "gemini" ? "https://generativelanguage.googleapis.com/v1beta/openai" : "https://api.openai.com/v1";
                advancedLocal.Checked = id == "lmstudio" && keyConfigured && savedProvider == "lmstudio";
                answerState.Text = "Settings changed. Load models and save your choice.";
                UpdateState();
            };
            model.SelectedIndexChanged += delegate { if (!initialising) { providerSaved = false; bridgeReady = false; answerState.Text = "Model selection changed. Save your answer settings."; } UpdateState(); };
            providerUrl.TextChanged += delegate { if (!initialising) { providerSaved = false; bridgeReady = false; answerState.Text = "API address changed. Load models and save your answer settings."; } UpdateState(); };
            apiKey.TextChanged += delegate { if (!initialising) { providerSaved = false; bridgeReady = false; answerState.Text = "API key changed. Save your answer settings."; } UpdateState(); };
            onlineConsent.CheckedChanged += delegate { UpdateState(); };
        }

        private void BuildVoice()
        {
            TableLayoutPanel page = Page("Give Franky a voice", "The speech models are bundled. Check that they are ready, then play a short preview through this PC's speakers.");
            AddText(page, "Preparing the voice checks and loads the local speech tools. Internet access may be needed to repair missing files. No cloud chat provider is called for this step.");
            FlowLayoutPanel row = ButtonRow(page);
            Action(row, "Prepare Franky's voice", async delegate
            {
                Dictionary<string, object> data = await RunAction("prepare_voice", null, "Checking and preparing speech tools…");
                voicePrepared = data != null;
                if (data != null) voiceState.Text = "Speech preparation passed. Play the preview to check your PC speakers.";
                else { bridgeReady = false; voiceState.Text = "Speech preparation needs attention. Review the message below and try again."; }
                UpdateState();
            });
            previewButton = Action(row, "Play voice preview", Preview);
            AddState(page, voiceState, "Speech preparation has not been checked yet.");
            AddText(page, "You can choose another voice later on Franky's voice page. PC preview playback does not test the robot's speaker; try a question on the robot after connecting it.");
        }

        private void BuildConnect()
        {
            TableLayoutPanel page = Page("A place on your home network", "The robot needs this PC's home-network address. LM Studio's port 1234 and the voice bridge's port 8766 have different jobs.");
            address.DropDownStyle = ComboBoxStyle.DropDown;
            AddField(page, "Robot / phone bridge address", address);
            ConfigureLabel(adapterHelp); adapterHelp.ForeColor = muted; page.Controls.Add(adapterHelp);
            address.SelectedIndexChanged += delegate { string caption; adapterHelp.Text = addressLabels.TryGetValue(address.Text, out caption) ? caption : ""; };
            address.TextChanged += delegate { if (!initialising) { addressSaved = false; bridgeReady = false; addressState.Text = "Address changed. Save it before continuing."; } UpdateState(); };
            FlowLayoutPanel row = ButtonRow(page);
            Action(row, "Find this PC's addresses", LoadAddresses);
            Action(row, "Save bridge address", async delegate
            {
                if (address.Text.Trim().Length == 0) { Explain("Choose or enter the PC's home-network address first."); return; }
                Dictionary<string, object> data = await RunAction("save_address", Fields("url", address.Text.Trim()), "Saving the robot-facing address…");
                if (data != null)
                {
                    initialising = true;
                    try { address.Text = TextOf(data, "url", address.Text.Trim()); }
                    finally { initialising = false; }
                    addressSaved = true; bridgeReady = false;
                    addressState.Text = "Saved. Copy this address into Franky's device settings."; UpdateState();
                }
            });
            Action(row, "Copy address", delegate { if (address.Text.Length > 0) Clipboard.SetText(address.Text); return Task.FromResult(0); });
            AddState(page, addressState, "No robot-facing address has been confirmed.");
            AddText(page, "Allow the robot through Windows Firewall\r\nThe button below adds access on Private networks for the local subnet only. Windows may ask for administrator approval. Choose your trusted home-network adapter, not a VPN address.");
            Action(ButtonRow(page), "Allow home-network access", async delegate { await RunAction("allow_firewall", null, "Requesting Windows Firewall approval…"); });
            AddText(page, "On the robot\r\nUse your home 2.4 GHz Wi-Fi. If Franky is in setup mode, join Wi-Fi DigitalRCS using password 11181118, then open http://192.168.4.1. Enter your Wi-Fi details and the bridge address above. After restarting, the robot's own settings page remains at the IP shown on its screen.");
        }

        private void BuildRobot()
        {
            TableLayoutPanel page = Page("Update the robot — optional", "Skip this step if Franky already runs the compatible firmware and works. Flashing replaces the robot's application; keep a private backup of existing firmware and settings.");
            AddText(page, "Only for the LAFVIN LA064 ESP32-S3 N16R8 kit. Connect it with a USB data cable and close Arduino or other serial monitors. Keep the robot connected until the update finishes.");
            ports.DropDownStyle = ComboBoxStyle.DropDownList;
            ports.DropDownWidth = 620;
            AddField(page, "Robot USB / COM port", ports);
            Action(ButtonRow(page), "Refresh USB ports", LoadPorts);
            boardConfirmed.Text = "I have the LAFVIN LA064 ESP32-S3 N16R8 kit and want to install the included firmware.";
            boardConfirmed.AutoSize = true;
            boardConfirmed.MaximumSize = new Size(660, 0);
            boardConfirmed.Dock = DockStyle.Fill;
            boardConfirmed.Margin = new Padding(0, 6, 0, 12);
            page.Controls.Add(boardConfirmed);
            inputControls.Add(boardConfirmed);
            FlowLayoutPanel row = ButtonRow(page);
            flashButton = Action(row, "Install robot firmware", Flash);
            Link(row, "USB driver help", "https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/get-started/establish-serial-connection.html");
            AddState(page, robotState, "No firmware update has been started.");
            AddText(page, "This wizard will not close while an update is running. Do not unplug the robot or switch off the PC. After the update, let Franky restart before trying a question.");
            boardConfirmed.CheckedChanged += delegate { UpdateState(); };
            ports.SelectedIndexChanged += delegate { UpdateState(); };
        }

        private void BuildTryIt()
        {
            TableLayoutPanel page = Page("Let's try a conversation", "Start the bridge, check its services, then use Franky's BOOT button or enabled Hello Franky wake phrase to ask a short question.");
            FlowLayoutPanel row = ButtonRow(page);
            Action(row, "Start bridge", StartBridge);
            Action(row, "Stop bridge", async delegate
            {
                if (await RunAction("stop_bridge", null, "Stopping the bridge…") != null)
                { bridgeReady = false; readyState.Text = "Bridge stopped."; readyDetails.Text = "Start the bridge again before using Franky."; UpdateState(); }
            });
            Action(row, "Check readiness", CheckReady);
            Action(row, "Open voice page", delegate { OpenUrl(bridgeUrl); return Task.FromResult(0); });
            AddState(page, readyState, "Readiness has not been checked yet.");
            ConfigureLabel(readyDetails); readyDetails.ForeColor = muted; page.Controls.Add(readyDetails);
            AddText(page, "When checks pass\r\nOpen the voice page to pick a voice, then try the robot. A successful service check confirms software availability; it does not prove that the robot heard you or that its speaker played correctly.");
            AddText(page, "If Franky stays quiet\r\nCheck that the PC and robot are on the same home network, the bridge address uses port 8766, and Windows Firewall allows home-network access. Keep LM Studio's model loaded when using local answers.");
        }

        private void BuildDone()
        {
            TableLayoutPanel page = Page("Your everyday routine", "Use the installed Start menu or desktop shortcuts to return to Franky. You can revisit any setup step without starting over.");
            AddState(page, doneState, "There are a few checks left.");
            ConfigureLabel(doneDetails); page.Controls.Add(doneDetails);
            AddText(page, "Each time you use Franky\r\n1. Keep this PC awake and connected to your home network.\r\n2. Start LM Studio and load the selected model if you use local answers.\r\n3. Start Franky's bridge, then check readiness.\r\n4. Switch on the robot and ask a question.");
            AddText(page, "To change something\r\nUse this wizard for provider and connection settings. Use the voice page for voice previews. Use the robot's own settings page for Wi-Fi, volume, brightness, and hands-free listening.");
            FlowLayoutPanel row = ButtonRow(page);
            Action(row, "Start bridge and open page", async delegate { await StartBridgeAndMaybeOpen(true); });
            Action(row, "Check installation again", Inspect);
        }

        private void ShowPage(int index)
        {
            if (index < 0 || index >= pages.Count) return;
            pageHost.SuspendLayout();
            pageHost.Controls.Clear();
            pageHost.Controls.Add(pages[index]);
            pageHost.AutoScrollPosition = Point.Empty;
            pageHost.ResumeLayout(true);
            WrapLabels();
            UpdateState();
        }

        private void WrapLabels()
        {
            if (navigation.SelectedIndex < 0 || navigation.SelectedIndex >= pages.Count) return;
            int width = Math.Max(260, pageHost.ClientSize.Width - 72);
            WrapChildren(pages[navigation.SelectedIndex], width);
        }

        private void WrapChildren(Control parent, int width)
        {
            foreach (Control control in parent.Controls)
            {
                if (control is Label || control is CheckBox) control.MaximumSize = new Size(width, 0);
                if (control is TableLayoutPanel) WrapChildren(control, width);
            }
        }

        private string ProviderId()
        {
            ProviderChoice choice = provider.SelectedItem as ProviderChoice;
            return choice == null ? "lmstudio" : choice.Id;
        }

        private void UpdateState()
        {
            bool local = ProviderId() == "lmstudio";
            bool existingKey = keyConfigured && savedProvider == ProviderId();
            foreach (Button button in actionButtons) button.Enabled = !busy;
            foreach (Control control in inputControls) control.Enabled = !busy;
            navigation.Enabled = !busy;
            back.Enabled = !busy && navigation.SelectedIndex > 0;
            next.Enabled = !busy && navigation.SelectedIndex < pages.Count - 1;
            providerUrl.ReadOnly = !local;
            onlineConsent.Enabled = !busy && !local;
            onlineConsent.Visible = !local;
            advancedLocal.Visible = local;
            if (providerUrlFields != null) providerUrlFields.Visible = local && advancedLocal.Checked;
            if (providerKeyFields != null) providerKeyFields.Visible = !local || advancedLocal.Checked;
            apiKey.Enabled = !busy;
            if (lmStudioButtons != null) lmStudioButtons.Visible = local;
            providerHelp.Text = local
                ? "Install LM Studio if needed, download and load a chat model there, then start its API server and click Find models."
                : "Online mode sends recognized conversation text to the selected provider. Speech recognition and voice generation stay local. OpenAI is metered; other providers have limits and may charge according to your account.";
            keyHelp.Text = existingKey ? "An existing saved key is available. Leave this box blank to keep it."
                : local ? "Only needed if you enabled authentication in LM Studio." : "Enter this provider's API key. It is hidden here and cleared after saving.";
            if (modelButton != null) modelButton.Enabled = !busy && (local || onlineConsent.Checked);
            if (saveProviderButton != null) saveProviderButton.Enabled = !busy && model.SelectedIndex >= 0 && (local || onlineConsent.Checked);
            if (previewButton != null) previewButton.Enabled = !busy && voicePrepared;
            if (flashButton != null) flashButton.Enabled = !busy && boardConfirmed.Checked && ports.SelectedItem is PortChoice;
            bool complete = providerSaved && voicePrepared && addressSaved && bridgeReady;
            doneState.Text = complete ? "Software checks passed. Try a question on Franky." : "Finish the remaining checks before using Franky.";
            doneDetails.Text = Mark(providerSaved, "Answer provider and model saved") + "\r\n" + Mark(voicePrepared, "Local speech prepared") + "\r\n" + Mark(addressSaved, "Robot-facing bridge address saved") + "\r\n" + Mark(bridgeReady, "Bridge readiness checks passed") + "\r\nFirmware update is optional. Test the robot's microphone and speaker in person.";
        }

        private static string Mark(bool done, string text) { return (done ? "Done — " : "Still to do — ") + text; }

        private async void OnShown(object sender, EventArgs e)
        {
            if (smokeTest) return;
            await Inspect();
            if (startOnOpen)
            {
                navigation.SelectedIndex = 5;
                await StartBridgeAndMaybeOpen(true);
            }
        }

        private async Task Inspect()
        {
            Dictionary<string, object> data = await RunAction("inspect", null, "Checking this installation…");
            if (data == null) return;
            initialising = true;
            try
            {
                savedProvider = TextOf(data, "provider", "lmstudio");
                apiKey.Clear();
                for (int i = 0; i < provider.Items.Count; i++) if (((ProviderChoice)provider.Items[i]).Id == savedProvider) provider.SelectedIndex = i;
                providerUrl.Text = TextOf(data, "base_url", "http://127.0.0.1:1234/v1");
                keyConfigured = BoolOf(data, "key_configured");
                Uri savedUrl;
                advancedLocal.Checked = savedProvider == "lmstudio" && (keyConfigured
                    || !Uri.TryCreate(providerUrl.Text, UriKind.Absolute, out savedUrl) || !savedUrl.IsLoopback);
                string selectedModel = TextOf(data, "model", "");
                model.Items.Clear();
                if (selectedModel.Length > 0) { model.Items.Add(selectedModel); model.SelectedIndex = 0; }
                providerSaved = selectedModel.Length > 0 && (savedProvider == "lmstudio" || keyConfigured);
                bool modelsPresent = BoolOf(data, "models_ready");
                voicePrepared = false;
                string publicUrl = TextOf(data, "public_bridge_url", "");
                FillAddresses(Items(data, "lan_addresses"), publicUrl);
                addressSaved = publicUrl.Length > 0;
                FillPorts(Items(data, "ports"));
                answerState.Text = providerSaved ? "Saved provider and model found. You can keep them or choose new settings." : "Choose a provider and model, then save.";
                voiceState.Text = modelsPresent ? "Bundled speech files are present. Prepare the voice and play a preview to verify this PC." : "Prepare the voice to check the bundled speech tools.";
                addressState.Text = addressSaved ? "Saved robot-facing address found." : "Choose this PC's home-network address and save it.";
                readyState.Text = BoolOf(data, "bridge_running") ? "Bridge is running. Use Check readiness for service status." : "Bridge is not running.";
                bridgeReady = false;
            }
            finally { initialising = false; UpdateState(); }
        }

        private Dictionary<string, object> ProviderFields()
        {
            Dictionary<string, object> fields = Fields("provider", ProviderId());
            fields["base_url"] = providerUrl.Text.Trim();
            fields["key"] = apiKey.Text.Trim();
            fields["online_consent"] = onlineConsent.Checked;
            return fields;
        }

        private bool ValidateProvider()
        {
            if (ProviderId() == "lmstudio")
            {
                if (providerUrl.Text.Trim().Length > 0) return true;
                Explain("Enter LM Studio's API address first."); return false;
            }
            if (!onlineConsent.Checked) { Explain("Read and select the online-provider consent checkbox before continuing."); return false; }
            if (apiKey.Text.Trim().Length == 0 && !(keyConfigured && savedProvider == ProviderId()))
            { Explain("Enter an API key for this provider first."); return false; }
            return true;
        }

        private async Task LoadModels()
        {
            if (!ValidateProvider()) return;
            Dictionary<string, object> data = await RunAction("models", ProviderFields(), "Loading available chat models…");
            if (data == null) return;
            string previous = model.SelectedItem as string;
            model.Items.Clear();
            foreach (object item in Items(data, "models")) if (item is string) model.Items.Add((string)item);
            if (previous != null && model.Items.Contains(previous)) model.SelectedItem = previous;
            else if (model.Items.Count > 0) model.SelectedIndex = 0;
            answerState.Text = model.Items.Count > 0 ? "Choose a chat model from the list, then save your settings." : "No chat models were found. Load a model in LM Studio or check the provider account.";
            UpdateState();
        }

        private async Task SaveProvider()
        {
            if (!ValidateProvider() || model.SelectedIndex < 0) return;
            Dictionary<string, object> fields = ProviderFields(); fields["model"] = model.SelectedItem.ToString();
            Dictionary<string, object> data;
            try { data = await RunAction("save_provider", fields, "Saving provider settings securely…"); }
            finally { apiKey.Clear(); }
            if (data != null)
            {
                bool keptKey = keyConfigured && savedProvider == ProviderId();
                providerSaved = true; savedProvider = ProviderId(); keyConfigured = ((string)fields["key"]).Length > 0 || keptKey;
                bridgeReady = false;
                answerState.Text = "Answer settings saved. Start the bridge on the Try it page.";
                UpdateState();
            }
        }

        private async Task Preview()
        {
            Dictionary<string, object> data = await RunAction("preview", null, "Preparing a short voice preview…");
            if (data == null) return;
            string path = TextOf(data, "path", "");
            try
            {
                if (!File.Exists(path)) throw new IOException();
                if (player != null) { player.Stop(); player.Dispose(); }
                player = new SoundPlayer(path);
                player.Load(); player.Play();
                voiceState.Text = "Preview sent to the PC speakers. Check that you can hear it; adjust Windows sound if needed.";
            }
            catch { Explain("The preview was prepared, but Windows could not play it. Check the PC's audio output and volume, then try again."); }
        }

        private async Task LoadAddresses()
        {
            Dictionary<string, object> data = await RunAction("lan_addresses", null, "Finding home-network addresses…");
            if (data != null) { initialising = true; try { FillAddresses(Items(data, "addresses"), address.Text); } finally { initialising = false; } UpdateState(); }
        }

        private void FillAddresses(IEnumerable items, string selected)
        {
            address.Items.Clear(); addressLabels.Clear();
            foreach (object item in items)
            {
                Dictionary<string, object> entry = item as Dictionary<string, object>;
                if (entry == null) continue;
                string url = TextOf(entry, "url", "");
                if (url.Length == 0) continue;
                address.Items.Add(url); addressLabels[url] = TextOf(entry, "label", "Home-network adapter");
            }
            address.Text = selected;
            string label;
            adapterHelp.Text = addressLabels.TryGetValue(selected, out label) ? label : "Choose your home-network adapter. You may also enter the server's LAN address manually.";
        }

        private async Task LoadPorts()
        {
            Dictionary<string, object> data = await RunAction("list_ports", null, "Finding connected USB ports…");
            if (data != null) { FillPorts(Items(data, "ports")); UpdateState(); }
        }

        private void FillPorts(IEnumerable items)
        {
            PortChoice previous = ports.SelectedItem as PortChoice;
            ports.Items.Clear();
            foreach (object item in items)
            {
                Dictionary<string, object> entry = item as Dictionary<string, object>;
                if (entry == null) continue;
                string port = TextOf(entry, "port", "");
                if (port.Length == 0) continue;
                PortChoice choice = new PortChoice(); choice.Port = port; choice.Description = TextOf(entry, "description", "");
                ports.Items.Add(choice);
                if (previous != null && previous.Port == port) ports.SelectedItem = choice;
            }
            if (ports.SelectedIndex < 0 && ports.Items.Count == 1) ports.SelectedIndex = 0;
            robotState.Text = ports.Items.Count == 0 ? "No USB ports found. Connect a USB data cable and refresh, or skip this optional step." : "Choose the robot's port carefully before updating.";
        }

        private async Task Flash()
        {
            PortChoice selected = ports.SelectedItem as PortChoice;
            if (selected == null || !boardConfirmed.Checked) return;
            if (MessageBox.Show(this, "Install the included firmware on " + selected.Port + "?\r\n\r\nConfirm this is your LA064 ESP32-S3 N16R8 robot. Keep the USB cable connected until the update finishes.",
                "Update Franky firmware", MessageBoxButtons.YesNo, MessageBoxIcon.Warning, MessageBoxDefaultButton.Button2) != DialogResult.Yes) return;
            Dictionary<string, object> fields = Fields("port", selected.Port); fields["confirmed"] = true;
            Dictionary<string, object> data = await RunAction("flash", fields, "Updating Franky. Keep the USB cable connected…");
            if (data != null) robotState.Text = "Firmware update completed" + (TextOf(data, "version", "").Length > 0 ? " — " + TextOf(data, "version", "") : "") + ". Let the robot restart, then test it.";
        }

        private async Task StartBridge()
        {
            await StartBridgeAndMaybeOpen(false);
        }

        private async Task StartBridgeAndMaybeOpen(bool openPage)
        {
            Dictionary<string, object> data = await RunAction("start_bridge", null, "Starting Franky's voice bridge…");
            if (data != null) { RememberBridgeUrl(data); if (openPage) OpenUrl(bridgeUrl); readyState.Text = "Bridge started. Checking services…"; await CheckReady(); }
        }

        private void RememberBridgeUrl(Dictionary<string, object> data)
        {
            string value = TextOf(data, "url", "");
            Uri uri;
            if (Uri.TryCreate(value, UriKind.Absolute, out uri) && (uri.Scheme == "http" || uri.Scheme == "https")) bridgeUrl = value;
        }

        private async Task CheckReady()
        {
            Dictionary<string, object> data = await RunAction("check_ready", null, "Checking bridge services…");
            if (data == null) { bridgeReady = false; readyState.Text = "Readiness check did not pass. Start the bridge and try again."; UpdateState(); return; }
            string state = TextOf(data, "status", "degraded");
            bridgeReady = state == "ready";
            readyState.Text = bridgeReady ? "Software availability checks passed." : state == "starting" ? "Speech services are still starting. Check again in a moment." : "Some services need attention.";
            Dictionary<string, object> checks = ObjectOf(data, "checks");
            if (TextOf(ObjectOf(checks, "voice"), "status", "") == "ready" && TextOf(ObjectOf(checks, "recognition"), "status", "") == "ready")
            {
                voicePrepared = true;
                voiceState.Text = "The running bridge has loaded speech recognition and voice. Play a preview to check your PC speakers.";
            }
            StringBuilder details = new StringBuilder();
            string[] keys = { "recognition", "voice", "chat" };
            string[] names = { "Speech recognition", "Voice", "Chat model" };
            for (int i = 0; i < keys.Length; i++)
            {
                Dictionary<string, object> check = ObjectOf(checks, keys[i]);
                details.AppendLine(names[i] + ": " + TextOf(check, "message", "Not checked"));
            }
            readyDetails.Text = details.ToString().TrimEnd();
            UpdateState();
        }

        private async Task<Dictionary<string, object>> RunAction(string action, Dictionary<string, object> fields, string message)
        {
            if (busy) return null;
            Dictionary<string, object> request = fields == null ? new Dictionary<string, object>() : new Dictionary<string, object>(fields);
            request["action"] = action;
            string sensitive = TextOf(request, "key", "");
            busy = true; status.Text = message; progress.Style = ProgressBarStyle.Marquee; UpdateState();
            IProgress<WorkerProgress> updates = new Progress<WorkerProgress>(delegate(WorkerProgress update)
            {
                if (IsDisposed) return;
                status.Text = SafeMessage(update.Message, sensitive, 320);
                if (update.Percent >= 0) { progress.Style = ProgressBarStyle.Continuous; progress.Value = Math.Max(0, Math.Min(100, update.Percent)); }
            });
            try
            {
                WorkerResult result = await Task.Run(delegate { return RunWorker(request, updates); });
                progress.Style = ProgressBarStyle.Continuous;
                progress.Value = result.Ok ? 100 : 0;
                if (!result.Ok)
                {
                    string error = SafeMessage(result.Error, sensitive, 1400);
                    status.Text = error;
                    MessageBox.Show(this, error, "Franky needs attention", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    return null;
                }
                status.Text = "Step finished. Review the result above, then continue when you're ready.";
                return result.Data;
            }
            catch
            {
                status.Text = "This task could not finish. Please try again.";
                Explain("Franky could not run this setup task. Check that the installation is complete, then try again. If this keeps happening, rerun the installer.");
                return null;
            }
            finally { busy = false; progress.Style = ProgressBarStyle.Continuous; UpdateState(); }
        }

        private WorkerResult RunWorker(Dictionary<string, object> request, IProgress<WorkerProgress> updates)
        {
            string python = Path.Combine(root, ".runtime", "python.exe");
            if (!File.Exists(python)) python = Path.Combine(root, ".venv", "Scripts", "python.exe");
            string worker = Path.Combine(root, "installer", "worker.py");
            if (!File.Exists(python) || !File.Exists(worker)) return Failure("The bundled setup tools are missing. Rerun the Franky installer to repair this installation.");
            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = python;
            info.Arguments = "-I -X utf8 -u \"" + worker + "\"";
            info.WorkingDirectory = root;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.WindowStyle = ProcessWindowStyle.Hidden;
            info.RedirectStandardInput = true;
            info.RedirectStandardOutput = true;
            info.RedirectStandardError = true;
            info.StandardOutputEncoding = new UTF8Encoding(false);
            info.StandardErrorEncoding = new UTF8Encoding(false);
            info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            info.EnvironmentVariables["PYTHONUTF8"] = "1";
            JavaScriptSerializer json = new JavaScriptSerializer();
            json.MaxJsonLength = 4 * 1024 * 1024;
            using (Process process = new Process())
            {
                process.StartInfo = info;
                process.Start();
                Task drain = DrainErrors(process.StandardError);
                byte[] payload = new UTF8Encoding(false).GetBytes(json.Serialize(request) + "\n");
                process.StandardInput.BaseStream.Write(payload, 0, payload.Length);
                process.StandardInput.BaseStream.Flush();
                process.StandardInput.Close();
                WorkerResult final = null;
                string line;
                while ((line = process.StandardOutput.ReadLine()) != null)
                {
                    Dictionary<string, object> record;
                    try { record = json.DeserializeObject(line) as Dictionary<string, object>; }
                    catch { continue; } // Never echo arbitrary subprocess output or secrets.
                    if (record == null) continue;
                    string type = TextOf(record, "type", "");
                    if (type == "progress")
                    {
                        WorkerProgress update = new WorkerProgress();
                        update.Message = TextOf(record, "message", "Working…");
                        object percent;
                        if (record.TryGetValue("percent", out percent)) { int parsed; if (Int32.TryParse(Convert.ToString(percent), out parsed)) update.Percent = parsed; }
                        updates.Report(update);
                    }
                    else if (type == "result")
                    {
                        final = new WorkerResult(); final.Ok = BoolOf(record, "ok"); final.Data = ObjectOf(record, "data");
                        final.Error = TextOf(record, "error", "The task did not finish. Review this step and try again.");
                    }
                }
                process.WaitForExit();
                drain.GetAwaiter().GetResult();
                if (final == null) return Failure("The setup task ended without a result. Please try again; do not disconnect the robot until any firmware update has finished.");
                if (process.ExitCode != 0 && final.Ok) return Failure("The setup task did not finish successfully. Please retry this step.");
                return final;
            }
        }

        private static async Task DrainErrors(StreamReader stream)
        {
            // Consume stderr so a full pipe cannot deadlock the worker. Never display or log it.
            while (await stream.ReadLineAsync().ConfigureAwait(false) != null) { }
        }

        private void OnClosing(object sender, FormClosingEventArgs e)
        {
            if (!busy) return;
            e.Cancel = true;
            MessageBox.Show(this, "A setup task is still running. Please leave this window open until it finishes.\r\n\r\nIf firmware is being installed, keep the robot connected throughout the update.",
                "Please let this step finish", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing && player != null) { player.Stop(); player.Dispose(); player = null; }
            base.Dispose(disposing);
        }

        private void Explain(string message) { MessageBox.Show(this, message, "Franky setup", MessageBoxButtons.OK, MessageBoxIcon.Information); }

        private void OpenUrl(string url)
        {
            Uri uri;
            if (!Uri.TryCreate(url, UriKind.Absolute, out uri) || (uri.Scheme != "http" && uri.Scheme != "https")) { Explain("The page address is not available yet. Start the bridge and try again."); return; }
            try { Process.Start(new ProcessStartInfo(url) { UseShellExecute = true }); }
            catch { Explain("Windows could not open the browser. Open this address manually:\r\n" + url); }
        }

        private static Dictionary<string, object> Fields(string key, object value)
        { Dictionary<string, object> result = new Dictionary<string, object>(); result[key] = value; return result; }
        private static string TextOf(Dictionary<string, object> data, string key, string fallback)
        { object value; return data != null && data.TryGetValue(key, out value) && value is string ? (string)value : fallback; }
        private static bool BoolOf(Dictionary<string, object> data, string key)
        { object value; return data != null && data.TryGetValue(key, out value) && value is bool && (bool)value; }
        private static Dictionary<string, object> ObjectOf(Dictionary<string, object> data, string key)
        { object value; return data != null && data.TryGetValue(key, out value) && value is Dictionary<string, object> ? (Dictionary<string, object>)value : new Dictionary<string, object>(); }
        private static IEnumerable Items(Dictionary<string, object> data, string key)
        { object value; return data != null && data.TryGetValue(key, out value) && value is IEnumerable && !(value is string) ? (IEnumerable)value : new object[0]; }
        private static WorkerResult Failure(string message) { WorkerResult result = new WorkerResult(); result.Error = message; return result; }
        private static string SafeMessage(string message, string secret, int limit)
        {
            string text = message ?? "Working…";
            if (!String.IsNullOrEmpty(secret)) text = text.Replace(secret, "[hidden]");
            return text.Length > limit ? text.Substring(0, limit) + "…" : text;
        }
    }
}
