// Native wizard state regressions; no worker, network, or hardware actions.
// Compile with .NET Framework csc and System.Windows.Forms.dll.
// Run: installer-ui-test.exe <path-to-compiled-FrankySetup.exe>
using System;
using System.Collections;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

internal static class InstallerUiTests
{
    private const BindingFlags PrivateInstance = BindingFlags.NonPublic | BindingFlags.Instance;
    private static int passed;

    private static T Field<T>(Form form, string name)
    {
        FieldInfo field = form.GetType().GetField(name, PrivateInstance);
        if (field == null) throw new InvalidOperationException("Missing wizard field: " + name);
        return (T)field.GetValue(form);
    }

    private static void Set(Form form, string name, object value)
    {
        FieldInfo field = form.GetType().GetField(name, PrivateInstance);
        if (field == null) throw new InvalidOperationException("Missing wizard field: " + name);
        field.SetValue(form, value);
    }

    private static void Update(Form form)
    {
        MethodInfo method = form.GetType().GetMethod("UpdateState", PrivateInstance);
        if (method == null) throw new InvalidOperationException("Missing wizard state update method");
        method.Invoke(form, null);
    }

    private static void Check(bool condition, string name)
    {
        if (!condition) throw new InvalidOperationException(name);
        passed++;
        Console.WriteLine("PASS: " + name);
    }

    private static bool AllDisabled(IEnumerable controls)
    {
        foreach (Control control in controls) if (control.Enabled) return false;
        return true;
    }

    private static void SavedAnswers(Form form)
    {
        Set(form, "providerSaved", true);
        Set(form, "bridgeReady", true);
    }

    private static bool AnswersInvalidated(Form form)
    {
        return !Field<bool>(form, "providerSaved") && !Field<bool>(form, "bridgeReady");
    }

    [STAThread]
    private static int Main(string[] args)
    {
        if (args.Length != 1 || !File.Exists(args[0]))
        {
            Console.Error.WriteLine("Usage: installer-ui-test.exe <compiled-FrankySetup.exe>");
            return 2;
        }
        try
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Assembly wizard = Assembly.LoadFrom(Path.GetFullPath(args[0]));
            Type formType = wizard.GetType("DigitalRCS.Franky.SetupForm", true);
            using (Form form = (Form)Activator.CreateInstance(formType, new object[] { false, true }))
            {
                // Stay hidden: never show the form, invoke OnShown, or click a task button.
                form.CreateControl();
                ListBox navigation = Field<ListBox>(form, "navigation");
                Button back = Field<Button>(form, "back"), next = Field<Button>(form, "next");
                navigation.SelectedIndex = 0;
                Update(form);
                Check(!back.Enabled && next.Enabled, "first-page navigation bounds");
                navigation.SelectedIndex = 6;
                Update(form);
                Check(back.Enabled && !next.Enabled, "last-page navigation bounds");

                SavedAnswers(form);
                Set(form, "voicePrepared", true);
                Set(form, "addressSaved", true);
                Set(form, "bridgeReady", false);
                Update(form);
                Check(Field<Label>(form, "doneState").Text.StartsWith("Finish"), "incomplete readiness prevents completion claim");
                Set(form, "bridgeReady", true);
                Update(form);
                Check(Field<Label>(form, "doneState").Text.StartsWith("Software"), "all required checks allow qualified completion without flashing");

                SavedAnswers(form);
                Field<TextBox>(form, "providerUrl").Text = "http://model.example:1234/v1";
                Check(AnswersInvalidated(form), "URL edits invalidate saved acceptance");
                ComboBox models = Field<ComboBox>(form, "model");
                models.Items.Add("Synthetic model");
                SavedAnswers(form);
                models.SelectedIndex = 0;
                Check(AnswersInvalidated(form), "model edits invalidate saved acceptance");
                SavedAnswers(form);
                ComboBox provider = Field<ComboBox>(form, "provider");
                provider.SelectedIndex = 1;
                Check(AnswersInvalidated(form), "provider edits invalidate saved acceptance");
                provider.SelectedIndex = 0;
                Set(form, "addressSaved", true);
                Set(form, "bridgeReady", true);
                Field<ComboBox>(form, "address").Text = "http://192.0.2.20:8766";
                Check(!Field<bool>(form, "addressSaved") && !Field<bool>(form, "bridgeReady"), "address edits invalidate saved acceptance");
                SavedAnswers(form);
                TextBox key = Field<TextBox>(form, "apiKey");
                key.Text = "synthetic-not-a-real-key";
                Check(AnswersInvalidated(form), "key edits invalidate saved acceptance");
                key.Clear();

                Set(form, "busy", true);
                Update(form);
                Check(!navigation.Enabled && !back.Enabled && !next.Enabled
                    && AllDisabled(Field<IEnumerable>(form, "actionButtons"))
                    && AllDisabled(Field<IEnumerable>(form, "inputControls")), "busy state locks navigation, actions, and inputs");
                Button preview = Field<Button>(form, "previewButton");
                Check(!preview.Enabled, "busy state disables preview");
                Set(form, "busy", false);
                Set(form, "voicePrepared", false);
                Update(form);
                Check(!preview.Enabled, "unprepared voice disables preview");
                Set(form, "voicePrepared", true);
                Update(form);
                Check(preview.Enabled, "prepared voice enables preview");

                ComboBox ports = Field<ComboBox>(form, "ports");
                CheckBox confirmed = Field<CheckBox>(form, "boardConfirmed");
                object port = Activator.CreateInstance(wizard.GetType("DigitalRCS.Franky.PortChoice", true));
                port.GetType().GetField("Port").SetValue(port, "COM99");
                port.GetType().GetField("Description").SetValue(port, "Synthetic test port");
                ports.Items.Add(port);
                ports.SelectedItem = port;
                confirmed.Checked = false;
                Update(form);
                Button flash = Field<Button>(form, "flashButton");
                Check(!flash.Enabled, "port alone cannot enable flash");
                confirmed.Checked = true;
                Update(form);
                Check(flash.Enabled, "explicit board confirmation and port enable flash");
                Set(form, "busy", true);
                Update(form);
                Check(!flash.Enabled, "busy state disables flash");
            }
            Console.WriteLine("Passed " + passed + " native UI-state checks; no task buttons were invoked.");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine("FAIL after " + passed + " checks: " + error.GetBaseException().Message);
            return 1;
        }
    }
}
