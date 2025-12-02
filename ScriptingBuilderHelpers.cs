#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Reflection;
using System.Text.RegularExpressions;
using System.Threading;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;
using Sabresaurus.PlayerPrefsUtilities;
using UnityEditor.AddressableAssets;
using UnityEditor.AddressableAssets.Settings;
using UnityEditor.AddressableAssets.Build;
using UnityEditor.AddressableAssets.Settings.GroupSchemas;
using UnityEditor.Callbacks;
using static UnityEditor.EditorApplication;
using Debug = UnityEngine.Debug;
using UnityEditor.Compilation;
using UnityEngine.AddressableAssets;
using UnityEditor.AddressableAssets.Build.DataBuilders;
using Newtonsoft.Json;

#if UNITY_ANDROID
using UnityEditor.Android;
using GooglePlayServices;
#endif
 
[System.Serializable]
public class EnvData
{
    public List<string> env_id;
    public List<string> bucket_id;
}

[System.Serializable]
public class KeystorePathsPass
{
    public PathData PATHS;
    public PassData PASS;
}

[System.Serializable]
public class PathData
{
    public string QA_KEYSTORE_PATH;
    public string PRODUCTION_KEYSTORE_PATH;
    public string STAGING_KEYSTORE_PATH;
    public string DEVELOP_KEYSTORE_PATH;
}
[System.Serializable]
public class PassData
{
    public string QA_KEYSTORE_PASS;
    public string PRODUCTION_KEYSTORE_PASS;
    public string STAGING_KEYSTORE_PASS;
    public string DEVELOP_KEYSTORE_PASS;
}

[Serializable]
public class EnvironmentPayload
{
    public string environment;
    public string timestamp;
}

public static class ScriptingBuilderHelpers
{
    //Unity Build Helper - START
    private static string AddressableStatePath(string os)
    {
        return os switch
        {
            "Darwin" => "/Users/dreamteamadmin/Projects/changokushi-heroes-client/Library/com.unity.addressables/BuildScript/content_state.bin",
            "Windows" => @"C:\Users\User\Desktop\Project Folder\changokushi-heroes-client\Library\com.unity.addressables\BuildScript\content_state.bin",
            _ => ""
        };
    }
    
    private static string AddressableUpdatePath(string os, string platform)
    {
        var env = GetEnvironment(false);
        return os switch
        {
            "Darwin" => $"/Users/dreamteamadmin/Projects/changokushi-heroes-client/Library/com.unity.addressables/AddressablesBuildCache/{platform}/{env}/content_state.bin",
            "Windows" => @$"C:\Users\User\Desktop\Project Folder\changokushi-heroes-client\Library\com.unity.addressables\AddressablesBuildCache\{platform}\{env}\content_state.bin",
            _ => ""
        };
    }

    private static string OutputPathAssign(string os, bool isIOS, string shotEnvId, string version, string note)
    {
        var envShort = GetEnvironment(true);
        return os switch
        {
            "Darwin" => isIOS
                ? $"/Users/dreamteamadmin/Projects/builds/iOS/{envShort}/ch-client-{shotEnvId}-{version}_{note}"
                : $"/Users/dreamteamadmin/Projects/builds/Android/{envShort}/ch-client-{shotEnvId}-{version}_{note}",
            "Windows" => @"C:\cdc-builds",
            _ => ""
        };
    }
    
    private static string OutputPathAddressableAssign(string os, bool isIOS)
    {
        var env = GetEnvironment(false);
        return os switch
        {
            "Darwin" => $"/Users/dreamteamadmin/Projects/keystore/{env}/Secured-Keys-{env}/ch-ks-{env}-upload.keystore",
            "Windows" => @$"C:\cdc-custom-keystore\Secured-Key-{env}\ch-ks-{env}-upload.keystore",
            _ => ""
        };
    }
    
    private static string[] GetEnabledScenes()
    {
        var scenes = new List<string>();
        EditorBuildSettings.scenes.ToList().ForEach(scene =>
        {
            if (scene.enabled)
                scenes.Add(scene.path);
        });
        return scenes.ToArray();
    }
    
    private static string GetArgForExternal(string name, string[] args)
    {
        for (var i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == name)
                return args[i + 1];
        }
        return null;
    }
    
    private static string MethodParamsForExternal(string search)
    {
        var args = Environment.GetCommandLineArgs();
        var result = GetArgForExternal(search, args);
        return result;
    }

    private static EnvData GetEnvData(string raw)
    {
        if (raw.StartsWith("\"") && raw.EndsWith("\""))
            raw = raw.Substring(1, raw.Length - 2);
        raw = raw.Replace("\\\"", "\"");
        var data = JsonUtility.FromJson<EnvData>(raw);
        return data;
    }

    private static void SetupPackageName(string environmentName)
    {
        var basePackage = "jp.okakichi.heroes";
        var buildTarget = NamedBuildTarget.FromBuildTargetGroup(EditorUserBuildSettings.selectedBuildTargetGroup);

        switch (environmentName)
        {
            case "PRODUCTION_ENV":
                PlayerSettings.SetApplicationIdentifier(buildTarget, basePackage);
                break;
            case "DEVELOP_ENV":
                PlayerSettings.SetApplicationIdentifier(buildTarget, basePackage + ".dev");
                break;
            case "QA_ENV":
                PlayerSettings.SetApplicationIdentifier(buildTarget, basePackage + ".qa");
                break;
            case "STAGING_ENV":
                PlayerSettings.SetApplicationIdentifier(buildTarget, basePackage + ".staging");
                break;
            default:
                PlayerSettings.SetApplicationIdentifier(buildTarget, basePackage + ".dev");
                break;
        }
    }

    private static string CheckDirectoryEnvId(string eightDigit)
    {
        return eightDigit switch
        {
            "7c9b7696" => "QA_ENV",
            "c5df4fe6" => "PRODUCTION",
            "c8bdd6b3" => "STAGING_ENV",
            "7fcfdc7a" => "DEVELOP",
            _ => ""
        };
    }

    private static string FindAndConnectWithDevice()
    {
        try
        {
            var adbPath = PlayerPrefs.GetString("ADB_PATH");
            var adb = new Process();
            adb.StartInfo.FileName = adbPath;
            adb.StartInfo.Arguments = "devices";
            adb.StartInfo.RedirectStandardOutput = true;
            adb.StartInfo.UseShellExecute = false;
            adb.StartInfo.CreateNoWindow = true;
            adb.Start();
            var output = adb.StandardOutput.ReadToEnd();
            adb.WaitForExit();
            
            foreach (var line in output.Split('\n'))
            {
                if (line.Contains("\tdevice"))
                {
                    Debug.Log(line.Split('\t')[0].Trim());
                    return line.Split('\t')[0].Trim();
                }
            }
        }
        catch (Exception e)
        {
            Debug.LogWarning("ADB check failed: " + e.Message);
        }

        return null;
    }
    
    public static string GetEnvironment(bool getShort)
    {
#if PRODUCTION_ENV
            return getShort ? "production" : "PRODUCTION_ENV";
#elif DEVELOP_ENV
            return getShort ? "dev" : "DEVELOP_ENV";
#elif QA_ENV
            return getShort ? "qa" : "QA_ENV";
#elif STAGING_ENV
            return getShort ? "staging" : "STAGING_ENV";
#else
            return null;
#endif
    }
    
    public static void RemoteGetEnvironment()
    {
        var env = PlayerPrefs.GetString("CURRENT_ENV", "NONE");
        Debug.Log($"[ENV] {env}");
    }
    
    private static void SetupEnvironment(string environmentName, string playerPrefsJson)
    {
        var allEnvs = new[]{ "PRODUCTION_ENV","STAGING_ENV","QA_ENV","DEVELOP_ENV" };
        foreach (BuildTargetGroup g in Enum.GetValues(typeof(BuildTargetGroup)))
        {
            if (g == BuildTargetGroup.Unknown) continue;

            try
            {
                var defs = PlayerSettings
                    .GetScriptingDefineSymbolsForGroup(g)
                    .Split(';')
                    .Where(s => !allEnvs.Contains(s))
                    .ToList();
                defs.Add(environmentName);
                PlayerSettings.SetScriptingDefineSymbolsForGroup(
                    g,
                    string.Join(";", defs)
                );
            }
            catch (ArgumentException)
            {
                Debug.Log($"[SWITCH] Skipping unsupported BuildTargetGroup: {g}");
            }
        }

        CheckAndAddPlayerPrefLocal(playerPrefsJson);
        var bucket = environmentName switch
        {
            "PRODUCTION_ENV" => "production",
            "STAGING_ENV" => "staging",
            "QA_ENV" => "qa",
            "DEVELOP_ENV" => "develop",
            _ => environmentName.ToLowerInvariant().Replace("_env", "")
        };
        
        Caching.ClearCache();
        Addressables.ClearResourceLocators();

        var settings = AddressableAssetSettingsDefaultObject.Settings;
        if (settings == null)
            throw new InvalidOperationException("Addressables settings asset not found!");

        var profileId = settings.profileSettings.GetProfileId(bucket);
        settings.activeProfileId = profileId;

        EditorUtility.SetDirty(settings);
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
    }

    public static void SwitchEnvironment()
    {
        var env       = MethodParamsForExternal("--value1");
        var scriptDir = MethodParamsForExternal("--value2");
        var playerPrefsJson = MethodParamsForExternal("--value3");
        var fullPath = Path.Combine(scriptDir, "main_data_payload.json");
        if (!string.IsNullOrEmpty(env) && !string.IsNullOrEmpty(fullPath))
        {
            var payloadJson = JsonUtility.ToJson(
                new EnvironmentPayload { environment = env, timestamp = DateTime.UtcNow.ToString("o") },
                prettyPrint: true
            );
            try
            {
                File.WriteAllText(fullPath, payloadJson);
                Debug.Log($"[SWITCH] Environment switched to {env}");
            }
            catch (Exception ex) { Debug.LogError($"[SWITCH] Failed to write payload JSON: {ex}"); }
        }
        else
            Debug.LogWarning($"[SWITCH] Missing data - Env: {env}, Path: {fullPath}");
        EditorPrefs.SetString("CURRENT_ENV", env);
        PlayerPrefs.Save();
        SetupEnvironment(env, playerPrefsJson);
    }
    
    private static void SetIfMissing(string pathKey, string pathValue, string passValue)
    {
        if (!pathKey.EndsWith("_PATH")) return;
        if (PlayerPrefs.HasKey(pathKey)) return;
        
        PlayerPrefs.SetString(pathKey, pathValue?.Trim());

        var passKey = pathKey.Replace("_PATH", "_PASS");
        PlayerPrefsUtility.SetEncryptedString(passKey, passValue);
    }

    public static void ForceScriptRecompile()
    {
        CompilationPipeline.RequestScriptCompilation();
    }

    public static void AddPlayerPref()
    {
        var playerPrefsJson = MethodParamsForExternal("--value1");
        var prefs = JsonUtility.FromJson<KeystorePathsPass>(playerPrefsJson);

        SetIfMissing("QA_KEYSTORE_PATH", prefs.PATHS.QA_KEYSTORE_PATH, prefs.PASS.QA_KEYSTORE_PASS);
        SetIfMissing("PRODUCTION_KEYSTORE_PATH", prefs.PATHS.PRODUCTION_KEYSTORE_PATH, prefs.PASS.PRODUCTION_KEYSTORE_PASS);
        SetIfMissing("STAGING_KEYSTORE_PATH", prefs.PATHS.STAGING_KEYSTORE_PATH, prefs.PASS.STAGING_KEYSTORE_PASS);
        SetIfMissing("DEVELOP_KEYSTORE_PATH", prefs.PATHS.DEVELOP_KEYSTORE_PATH, prefs.PASS.DEVELOP_KEYSTORE_PASS);
        PlayerPrefs.Save();
    }
    
    public static void CheckAndAddPlayerPrefLocal(string playerPrefsJson)
    {
        var prefs = JsonUtility.FromJson<KeystorePathsPass>(playerPrefsJson);

        SetIfMissing("QA_KEYSTORE_PATH", prefs.PATHS.QA_KEYSTORE_PATH, prefs.PASS.QA_KEYSTORE_PASS);
        SetIfMissing("PRODUCTION_KEYSTORE_PATH", prefs.PATHS.PRODUCTION_KEYSTORE_PATH, prefs.PASS.PRODUCTION_KEYSTORE_PASS);
        SetIfMissing("STAGING_KEYSTORE_PATH", prefs.PATHS.STAGING_KEYSTORE_PATH, prefs.PASS.STAGING_KEYSTORE_PASS);
        SetIfMissing("DEVELOP_KEYSTORE_PATH", prefs.PATHS.DEVELOP_KEYSTORE_PATH, prefs.PASS.DEVELOP_KEYSTORE_PASS);
        PlayerPrefs.Save();
        
        var env = GetEnvironment(false);
        var envShort = GetEnvironment(true);
        
        ScriptingDefineSymbolsHelper.SetKeystore(env);
        
#if PRODUCTION_ENV
        var currentKeystorePath = prefs.PATHS.PRODUCTION_KEYSTORE_PATH;
        var currentKeystorePass = prefs.PASS.PRODUCTION_KEYSTORE_PASS;
#elif DEVELOP_ENV
        var currentKeystorePath = prefs.PATHS.DEVELOP_KEYSTORE_PATH;
        var currentKeystorePass = prefs.PASS.DEVELOP_KEYSTORE_PASS;
#elif QA_ENV
        var currentKeystorePath = prefs.PATHS.QA_KEYSTORE_PATH;
        var currentKeystorePass = prefs.PASS.QA_KEYSTORE_PASS;
#elif STAGING_ENV
        var currentKeystorePath = prefs.PATHS.STAGING_KEYSTORE_PATH;
        var currentKeystorePass = prefs.PASS.STAGING_KEYSTORE_PASS;
#else
        Debug.LogWarning($"Unknown environment: {env}");
#endif
        
        
        PlayerSettings.Android.keystoreName = currentKeystorePath;
        PlayerSettings.Android.keystorePass = currentKeystorePass;
        PlayerSettings.Android.keyaliasName = $"ch-ks-{envShort}-upload-alias";
        PlayerSettings.Android.keyaliasPass = currentKeystorePass;
        
        AssetDatabase.SaveAssets();
    }

    private static string[] GetPlayerPrefsKeys(string playerPrefsJson)
    {
        var prefs = JsonUtility.FromJson<KeystorePathsPass>(playerPrefsJson);
        var env = GetEnvironment(false);

        return env switch
        {
            "PRODUCTION_ENV" => new string[] { prefs.PATHS.PRODUCTION_KEYSTORE_PATH, prefs.PASS.PRODUCTION_KEYSTORE_PASS },
            "DEVELOP_ENV" => new string[] { prefs.PATHS.DEVELOP_KEYSTORE_PATH, prefs.PASS.DEVELOP_KEYSTORE_PASS },
            "QA_ENV" => new string[] { prefs.PATHS.QA_KEYSTORE_PATH, prefs.PASS.QA_KEYSTORE_PASS },
            "STAGING_ENV" => new string[] { prefs.PATHS.STAGING_KEYSTORE_PATH, prefs.PASS.STAGING_KEYSTORE_PASS },
            _ => Array.Empty<string>()
        };
    }

    public static void AndroidResolver()
    {
#if UNITY_ANDROID
        PlayServicesResolver.DeleteResolvedLibraries();
        PlayServicesResolver.ResolveSync(true);
#endif
    }

    private static void CopyDirectoryRecursive(string sourceDir, string targetDir)
    {
        Directory.CreateDirectory(targetDir);

        foreach (var file in Directory.GetFiles(sourceDir, "*", SearchOption.AllDirectories))
        {
            var relative = file.Substring(sourceDir.Length + 1);
            var targetPath = Path.Combine(targetDir, relative);
            Directory.CreateDirectory(Path.GetDirectoryName(targetPath));
            File.Copy(file, targetPath, true);
        }
    }

    public static void BuildAddressable()
    {
        var envId = MethodParamsForExternal("--value1");
        var projectId = MethodParamsForExternal("--value2");
        var bucketId = MethodParamsForExternal("--value3");
        var buildTarget = MethodParamsForExternal("--value4");
        var version = MethodParamsForExternal("--value5");
        var platform = $"{buildTarget}/";
        
        var bucket = envId switch
        {
            "PRODUCTION_ENV" => "production",
            "STAGING_ENV" => "staging",
            "QA_ENV" => "qa",
            "DEVELOP_ENV" => "develop",
            _ => envId.ToLowerInvariant().Replace("_env", "")
        };
        BuildAddressables.GetSettingsObject();
        BuildAddressables.SetProfile(bucket);
        
        if (string.IsNullOrEmpty(envId) || string.IsNullOrEmpty(projectId) || string.IsNullOrEmpty(bucketId))
        {
            Debug.LogError("[BUILD FAILED!] Missing envId, projectId, or bucketId from external params.");
            return;
        }
        
        PlayerSettings.bundleVersion = version;
        
        if (buildTarget.Contains("iOS"))
            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.iOS, BuildTarget.iOS);
        else if (buildTarget.Contains("Android"))
            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);
        
        var settings = AddressableAssetSettingsDefaultObject.Settings;
        var profileId = settings.activeProfileId;

        var remotePath = $"https://{projectId}.client-api.unity3dusercontent.com/client_api/v1/environments/{envId}/buckets/{bucketId}/release_by_badge/latest/entry_by_path/content/?path={platform}";
        var localBuildPath = $"ServerData/{buildTarget}";
        Directory.CreateDirectory(localBuildPath);

        try { settings.profileSettings.SetValue(profileId, "BuildTarget", buildTarget); }
        catch (Exception) { settings.profileSettings.CreateValue("BuildTarget", buildTarget); }
        
        try { settings.profileSettings.SetValue(profileId, "RemoteURL", remotePath); }
        catch (Exception) { settings.profileSettings.CreateValue("RemoteURL", remotePath); }
        
        try { settings.profileSettings.SetValue(profileId, "LocalBuildPath", localBuildPath); }
        catch (Exception) { settings.profileSettings.CreateValue("LocalBuildPath", localBuildPath); }

        foreach (var group in settings.groups.Where(g => g != null && !g.ReadOnly))
        {
            var schema = group.GetSchema<BundledAssetGroupSchema>();
            if (schema == null) continue;

            schema.BuildPath.SetVariableByName(settings, "LocalBuildPath");
            schema.LoadPath.SetVariableByName(settings, "RemoteURL");

            schema.Compression = BundledAssetGroupSchema.BundleCompressionMode.LZ4;
            schema.UseAssetBundleCrc = false;
            schema.UseAssetBundleCache = true;

            schema.BundleMode = BundledAssetGroupSchema.BundlePackingMode.PackTogether;
            schema.IncludeGUIDInCatalog = true;
            schema.IncludeAddressInCatalog = true;
        }

        AddressableAssetSettings.CleanPlayerContent();
        AddressablesPlayerBuildResult result = null;
        
        try
        {
            var start = DateTime.Now;

            var builder = ScriptableObject.CreateInstance<BuildScriptPackedMode>();
            var input = new AddressablesDataBuilderInput(settings);
            result = builder.BuildData<AddressablesPlayerBuildResult>(input);
            var unityOutput = Path.Combine("Library/com.unity.addressables/aa", buildTarget);
            if (Directory.Exists(unityOutput))
                CopyDirectoryRecursive(unityOutput, localBuildPath);
            else
                Debug.LogWarning($"[Addressables] No build output found at: {unityOutput}");
            UnityEngine.Object.DestroyImmediate(builder);
            var duration = DateTime.Now - start;

            if (result == null)
                Debug.LogWarning("[Addressables] Build returned null result (fallback to timing only).");
            else if (!string.IsNullOrEmpty(result.Error))
                Debug.LogError($"[Addressables] Build failed: {result.Error}");

            var report = new
            {
                Environment = envId,
                Bucket = bucket,
                Version = version,
                Platform = buildTarget,
                TimeStamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"),
                DurationSeconds = result?.Duration ?? duration.TotalSeconds,
                Result = string.IsNullOrEmpty(result?.Error) ? "Success" : "Failed",
                Error = result?.Error,
                OutputPath = localBuildPath,
                Groups = settings.groups
                    .Where(g => g != null && !g.ReadOnly)
                    .Select(g =>
                    {
                        var schema = g.GetSchema<BundledAssetGroupSchema>();
                        return new
                        {
                            Name = g.Name,
                            Compression = schema?.Compression.ToString(),
                            BuildPath = schema?.BuildPath?.GetValue(settings),
                            LoadPath = schema?.LoadPath?.GetValue(settings),
                            BundleMode = schema?.BundleMode.ToString(),
                        };
                    })
                    .ToList(),
                TotalFileCount = Directory.Exists(localBuildPath)
                    ? Directory.GetFiles(localBuildPath, "*", SearchOption.AllDirectories).Length
                    : 0,
                TotalFileSizeMB = Directory.Exists(localBuildPath)
                    ? Directory.GetFiles(localBuildPath, "*", SearchOption.AllDirectories)
                        .Sum(f => new FileInfo(f).Length) / 1024f / 1024f
                    : 0f
            };

            var reportPath = Path.Combine(localBuildPath, "addressables_build_report.json");
            var json = JsonConvert.SerializeObject(report, Formatting.Indented);
            File.WriteAllText(reportPath, json, Encoding.UTF8);
            Debug.Log($"[REPORT SAVED] {reportPath}");
        }
        catch (Exception ex)
        {
            Debug.LogError($"[FAILED] Addressables build encountered an error: {ex.Message}");
        }
    }
    
    public static void PatchAddressable() 
    {
        var envId = MethodParamsForExternal("--value1");
        var os = MethodParamsForExternal("--value2");
        var platform = MethodParamsForExternal("--value3");

        if (platform == "iOS")
            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.iOS, BuildTarget.iOS);
        else if (platform == "Android")
            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);
        
        var buildStatePath = AddressableStatePath(os);
        var updatePath = AddressableUpdatePath(os, platform);
        var settings = AddressableAssetSettingsDefaultObject.Settings;
        try
        {
            var updateDir = Path.GetDirectoryName(updatePath) ?? string.Empty;
            Directory.CreateDirectory(updateDir);

            if (File.Exists(updatePath))
            {
                Debug.Log("[Addressables] Running content update build...");

                var modified = ContentUpdateScript.GatherModifiedEntries(settings, updatePath);
                if (modified.Count > 0)
                {
                    Debug.Log($"[Addressables] {modified.Count} assets modified since last build.");
                    ContentUpdateScript.CreateContentUpdateGroup(settings, modified, "Content Update Group");
                }
                else
                {
                    Debug.Log("[Addressables] No assets modified. Skipping content update.");
                    return;
                }

                AddressableAssetSettings.BuildPlayerContent(out var result);

                if (File.Exists(buildStatePath))
                {
                    File.Copy(buildStatePath, updatePath, true);
                    Debug.Log($"[Addressables] Updated content_state.bin at {updatePath}");
                }
                else
                {
                    Debug.LogWarning("[Addressables] Warning: build succeeded but no content_state.bin was found.");
                }
            }
            else
            {
                Debug.Log("[Addressables] No previous snapshot — doing full build...");
                AddressableAssetSettings.CleanPlayerContent();
                AddressableAssetSettings.BuildPlayerContent(out var result);

                if (File.Exists(buildStatePath))
                {
                    File.Copy(buildStatePath, updatePath, true);
                    Debug.Log($"[Addressables] Created content_state.bin at {updatePath}");
                }
                else
                {
                    Debug.LogWarning("[Addressables] Warning: build succeeded but no content_state.bin was found.");
                }
            }
        }
        catch (Exception ex)
        {
            Debug.LogError($"[FAILED] Addressables build error: {ex.Message}");
        }
    }

    public static void BuildAddressableGroups()
    {
        var args = Environment.GetCommandLineArgs();
        var groupArg = args.FirstOrDefault(a => a.StartsWith("-groups="));
        var outputPathArg = args.FirstOrDefault(a => a.StartsWith("-outputPath="));

        if (string.IsNullOrEmpty(groupArg) || string.IsNullOrEmpty(outputPathArg))
        {
            Debug.LogError("Missing -groups or -outputPath CLI argument");
            return;
        }

        var groupNames = groupArg?.Substring("-groups=".Length).Split(',');
        var outputPath = outputPathArg?.Substring("-outputPath=".Length);

        var settings = AddressableAssetSettingsDefaultObject.Settings;

        foreach (var groupName in groupNames)
        {
            if (settings.groups.All(g => g.Name != groupName))
            {
                Debug.LogError("Group not found: " + groupName);
                continue;
            }

            var group = settings.FindGroup(groupName);
            if (group == null)
            {
                Debug.LogWarning("Group not found: " + groupName);
                continue;
            }

            settings.RemoteCatalogBuildPath.SetVariableByName(settings, outputPath);
            settings.RemoteCatalogLoadPath.SetVariableByName(settings, outputPath);

            var input = new AddressablesDataBuilderInput(settings);

            IDataBuilder builder = ScriptableObject.CreateInstance<BuildScriptPackedMode>();
            var result = builder.BuildData<IDataBuilderResult>(input);

            if (result?.Error != null)
                Debug.LogError($"Failed to build group {groupName}: {result.Error}");
            else
                Debug.Log($"Built group: {groupName}");
        }
    }

    public static void GenerateAddressableData()
    {
        var args = Environment.GetCommandLineArgs();
        var outputDir = args.FirstOrDefault(arg => arg.StartsWith("-outputDir="))?.Substring("-outputDir=".Length);

        if (string.IsNullOrEmpty(outputDir))
        {
            Debug.LogError("Missing -outputDir CLI arg");
            return;
        }

        var catalogFilename = "catalog.json";
        var settingsJsonPath = Path.Combine(outputDir ?? string.Empty, "settings.json");
        var catalogAddressPath = Path.Combine(outputDir ?? string.Empty, "catalogAddress");

        var runtimeSettings = new
        {
            CatalogLocations = new[] {
                new {
                    Provider = "UnityEngine.ResourceManagement.ResourceProviders.ContentCatalogProvider",
                    Keys = new[] { catalogFilename },
                    InternalId = catalogFilename,
                    ResourceType = "UnityEngine.AddressableAssets.ResourceLocators.ContentCatalogData, Unity.Addressables"
                }
            },
            RemoteCatalog = true,
            BuildTarget = EditorUserBuildSettings.activeBuildTarget.ToString()
        };

        File.WriteAllText(settingsJsonPath, JsonUtility.ToJson(runtimeSettings, true));
        File.WriteAllText(catalogAddressPath, catalogFilename);
        Debug.Log("settings.json and catalogAddress generated");
    }

    public static void RemoteAndroidTestBuild()
    {
        var envId = MethodParamsForExternal("--value1");
        var version = MethodParamsForExternal("--value2");
        var note = MethodParamsForExternal("--value3");
        var pushToCloudVal = MethodParamsForExternal("--value4");
        var pushToCloud = pushToCloudVal == "1";
        var cloudApiKey = MethodParamsForExternal("--value5");
        var orgsId = MethodParamsForExternal("--value6");
        var projectId = MethodParamsForExternal("--value7");
        var envBucketId = MethodParamsForExternal("--value8");
        var currentOS = MethodParamsForExternal("--value9");
        var playerPrefsJson = MethodParamsForExternal("--value10");
        var platform = MethodParamsForExternal("--value11").Trim().ToLowerInvariant();
        var shortEnvId = MethodParamsForExternal("--value12");
        
        if (pushToCloud)
        {
            /*ccdApiUrl = $"https://services.api.unity.com/ccd/organizations/{orgsId}/projects/{projectId}/buckets";
            listUrl = $"https://services.api.unity.com/ccd/organizations/{orgsId}/projects/{projectId}/buckets/{bucketId}/releases/{relId}/entries";*/
            Debug.Log(pushToCloudVal+"\n"+cloudApiKey+"\n"+orgsId+"\n"+projectId+"\n"+envBucketId+"\n"+platform+"\n");
            return;
        }
        
        EditorPrefs.SetInt("UnityEditor.AssetImportWorkers", SystemInfo.processorCount);
        EditorPrefs.SetBool("CacheServerEnabled", true);
        EditorPrefs.SetString("CacheServerMode", "Local");
        PlayerSettings.stripEngineCode = true;
        EditorUserBuildSettings.development = true;
        EditorUserBuildSettings.allowDebugging = true;
        EditorUserBuildSettings.connectProfiler = true;
        if (platform == "android")
        {
            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            CompilationPipeline.RequestScriptCompilation();
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.useCustomKeystore = true;
            var outputPath = OutputPathAssign(currentOS, false, shortEnvId, version, note);
            if (File.Exists(outputPath)) File.Delete(outputPath);
            if (!Directory.Exists(outputPath)) Directory.CreateDirectory(outputPath);
            
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel22;
            PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel35;
            
            InputPopupWindow.SetEnvironment(envId);
            
            PlayerSettings.SetManagedStrippingLevel(BuildTargetGroup.Android, ManagedStrippingLevel.Low);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARMv7 | AndroidArchitecture.ARM64;
            EditorUserBuildSettings.androidBuildSystem = AndroidBuildSystem.Gradle;
            EditorUserBuildSettings.buildAppBundle = false;
            PlayerSettings.Android.bundleVersionCode = 1;
            PlayerSettings.Android.useAPKExpansionFiles = false;
            
            var apkName = $"ch-client-{shortEnvId}-{version}_{note}";
            var fullPath = Path.Combine(outputPath, apkName);
            Debug.Log("Output Path: " + outputPath);
            Debug.Log("APK Name: " + apkName);
            Debug.Log("Full Path: " + fullPath);
            Directory.CreateDirectory(Path.GetDirectoryName(fullPath) ?? string.Empty);
            
            var originalOut = Console.Out;
            Console.SetOut(TextWriter.Null);
            
            SetupPackageName(envId);
            ScriptingDefineSymbolsHelper.SetApplicationName(envId);
            ScriptingDefineSymbolsHelper.SetAppIcon(envId);
            BuildReport report = null;
            var scenes = GetEnabledScenes();
            if (scenes == null || scenes.Length == 0)
            {
                Debug.LogError("[BUILD ERROR] No scenes enabled in build settings.");
                return;
            }
            try {                     
                report = BuildPipeline.BuildPlayer(
                    scenes,
                    fullPath + ".apk",
                    BuildTarget.Android,
                    BuildOptions.None
                );
            }
            catch (IOException ioEx) { Debug.LogError($"[BUILD FAILED - IO ERROR] IOException during build: {ioEx.Message}"); return; }
            catch (Exception ex) { Debug.LogError($"[BUILD FAILED - EXCEPTION] Unexpected error during build: {ex.Message}"); return; }
            finally { Console.SetOut(originalOut); }
            var summary = report.summary;

            if (summary.result == BuildResult.Succeeded)
            {
                Debug.Log($"[BUILD SUCCESS!] Build succeeded: {summary.totalSize / 1_000_000f:F2} MB → {fullPath}");
                if (!File.Exists(fullPath))
                {
                    Debug.LogWarning("[WARNING] .aab not found at expected path after successful build. Attempting fallback...");
                    var candidates = Directory.GetFiles(outputPath, "*.aab", SearchOption.AllDirectories);
                    if (candidates.Length > 0)
                    {
                        var fallback = candidates.First();
                        File.Copy(fallback, fullPath, overwrite: true);
                        Debug.Log($"[INFO] Fallback .aab copied to expected path: {fullPath}");
                    }
                    else
                    {
                        Debug.LogError("[ERROR] No .aab file found even after fallback.");
                    }
                }
            }
            else
            {
                Debug.LogError($"[BUILD FAILED!] Build result: {summary.result}");
                foreach (var step in report.steps)
                {
                    foreach (var msg in step.messages)
                    {
                        if (msg.type == LogType.Error)
                            Debug.LogError($"[ERROR] {msg.content}");
                    }
                }
            }
                 
        }
        else if (platform == "ios")
        {
            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.iOS, BuildTarget.iOS);
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.iOS, ScriptingImplementation.IL2CPP);
            var setBundleVersion = version.Split("-")[1];

            PlayerSettings.iOS.buildNumber = "0";
            PlayerSettings.bundleVersion = setBundleVersion;

            var outputPath = OutputPathAssign(currentOS, true, shortEnvId, version, note);
            var fullPath = outputPath;

            var buildPlayerOptions = new BuildPlayerOptions
            {
                scenes = GetEnabledScenes(),
                locationPathName = fullPath,
                target = BuildTarget.iOS,
                options = BuildOptions.None
            };

            var report = BuildPipeline.BuildPlayer(buildPlayerOptions);
            var summary = report.summary;
            
            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);

            if (summary.result == BuildResult.Succeeded)
                Debug.Log($"[BUILD SUCCESS!] Test Build succeeded: {summary.totalSize / 1_000_000f:F2} MB → {fullPath}");
            else
            {
                Debug.LogError($"[BUILD FAILED!] Build result: {summary.result}");
                foreach (var step in report.steps)
                {
                    foreach (var msg in step.messages)
                    {
                        if (msg.type == LogType.Error)
                            Debug.LogError($"[ERROR] {msg.content}");
                    }
                }
            } 
        }
    }

    public static void RemoteAndroidPublicBuild()
    {
        var envId = MethodParamsForExternal("--value1");
        var versionCode = MethodParamsForExternal("--value2");
        var versionName = MethodParamsForExternal("--value3");
        var note = MethodParamsForExternal("--value4");
        var pushToCloudVal = MethodParamsForExternal("--value5");
        var cloudApiKey = MethodParamsForExternal("--value6");
        var orgsId = MethodParamsForExternal("--value7");
        var projectId = MethodParamsForExternal("--value8");
        var envBucketId = MethodParamsForExternal("--value9");
        var currentOS = MethodParamsForExternal("--value10");
        var playerPrefsJson = MethodParamsForExternal("--value11");
        var platform = MethodParamsForExternal("--value12").Trim().ToLowerInvariant();
        var shortEnvId = MethodParamsForExternal("--value13");
        var pushToCloud = pushToCloudVal == "1";
        if (pushToCloud)
        {
            /*ccdApiUrl = $"https://services.api.unity.com/ccd/organizations/{orgsId}/projects/{projectId}/buckets";
            listUrl = $"https://services.api.unity.com/ccd/organizations/{orgsId}/projects/{projectId}/buckets/{bucketId}/releases/{relId}/entries";*/
            Debug.Log(pushToCloudVal+"\n"+cloudApiKey+"\n"+orgsId+"\n"+projectId+"\n"+envBucketId+"\n"+platform+"\n");
            return;
        }
        
        EditorPrefs.SetInt("UnityEditor.AssetImportWorkers", SystemInfo.processorCount);
        EditorPrefs.SetBool("CacheServerEnabled", true);
        EditorPrefs.SetString("CacheServerMode", "Local");
        PlayerPrefs.SetInt("VersionCode", int.Parse(versionCode));
        var version = versionCode + "-" + versionName;
        
        if (platform == "android")
        {
            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);
            EditorUserBuildSettings.androidBuildSystem = AndroidBuildSystem.Gradle;
            EditorUserBuildSettings.buildAppBundle = true;
            EditorUserBuildSettings.exportAsGoogleAndroidProject = false;
            
            PlayerSettings.bundleVersion = versionName;

/*#if PLATFORM_ANDROID
            var type = typeof(PlayerSettings.Android);
            var prop = type.GetProperty("createSymbolsZip", BindingFlags.Static | BindingFlags.Public);
            if (prop != null)
                prop.SetValue(null, 1);
#endif*/

            var outputPath = OutputPathAssign(currentOS, false, shortEnvId, version, note);
            if (Directory.Exists(outputPath))
                Directory.Delete(outputPath, true);
            Directory.CreateDirectory(outputPath);

            var aabName   = $"ch-client-{shortEnvId}-{version}_{note}.aab";
            var fullAabPath = Path.Combine(outputPath, aabName);
            Debug.Log($"[BUILD] Output AAB path: {fullAabPath}");

            var scenes = GetEnabledScenes();
            if (scenes == null || scenes.Length == 0)
            {
                Debug.LogError("[BUILD ERROR] No scenes enabled in build settings.");
                return;
            }
            
#if UNITY_ANDROID
            PlayServicesResolver.DeleteResolvedLibraries();
            PlayServicesResolver.ResolveSync(true);
#endif
            
            const int maxRetries = 3;
            const int waitForAabSeconds = 120;
            var attempt = 0;
            var built = false;

            while (attempt < maxRetries && !built)
            {
                attempt++;
                Debug.Log($"[BUILD] Attempt #{attempt}/{maxRetries} – building AAB…");
                Debug.Log("Converting:" + int.Parse(versionCode));
                PlayerSettings.Android.bundleVersionCode = int.Parse(versionCode);
                PlayerSettings.bundleVersion = versionName;

#if PRODUCTION_ENV
                var currentKeystorePath = PlayerPrefs.GetString("PRODUCTION_KEYSTORE_PATH");
                var currentKeystorePass = PlayerPrefsUtility.GetEncryptedString("PRODUCTION_KEYSTORE_PASS");
#elif DEVELOP_ENV
                var currentKeystorePath = PlayerPrefs.GetString("DEVELOP_KEYSTORE_PATH");
                var currentKeystorePass = PlayerPrefsUtility.GetEncryptedString("DEVELOP_KEYSTORE_PASS");
#elif QA_ENV
                var currentKeystorePath = PlayerPrefs.GetString("QA_KEYSTORE_PATH");
                var currentKeystorePass = PlayerPrefsUtility.GetEncryptedString("QA_KEYSTORE_PASS");
#elif STAGING_ENV
                var currentKeystorePath = PlayerPrefs.GetString("STAGING_KEYSTORE_PATH");
                var currentKeystorePass = PlayerPrefsUtility.GetEncryptedString("STAGING_KEYSTORE_PASS");
#endif

                PlayerSettings.Android.keystoreName = currentKeystorePath;
                PlayerSettings.Android.keystorePass = currentKeystorePass;
                PlayerSettings.Android.keyaliasName = $"ch-ks-{shortEnvId}-upload-alias";
                PlayerSettings.Android.keyaliasPass = currentKeystorePass;
                
                var originalOut = Console.Out;
                try
                {
                    Console.SetOut(TextWriter.Null);

                    var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
                        scenes = scenes,
                        locationPathName = fullAabPath,
                        target = BuildTarget.Android,
                        options = BuildOptions.None
                    });
                    
                    var sw = Stopwatch.StartNew();
                    var foundAabs = Array.Empty<string>();
                    while (sw.Elapsed.TotalSeconds < waitForAabSeconds && foundAabs.Length == 0)
                    {
                        AssetDatabase.Refresh();
                        if (Directory.Exists(outputPath))
                            foundAabs = Directory.GetFiles(outputPath, "*.aab", SearchOption.AllDirectories);

                        if (foundAabs.Length == 0)
                            Thread.Sleep(1000);
                    }
                
                    if (report.summary.result == BuildResult.Succeeded && foundAabs.Length > 0)
                    {
                        Debug.Log($"[BUILD SUCCESS] AAB generated at: {foundAabs[0]}");
                        built = true;
                    }
                    else
                    {
                        Debug.LogWarning($"[BUILD] No .aab found after attempt #{attempt}. Retrying…");
                        if (Directory.Exists(outputPath))
                            FileUtil.DeleteFileOrDirectory(outputPath);
                        Thread.Sleep(2000);
                    }
                }
                catch (IOException ioEx) { Debug.LogError($"[BUILD FAILED] {ioEx.Message}"); return; }
                catch (Exception ex) { Debug.LogError($"[BUILD FAILED] {ex.Message}"); return; }
                finally { Console.SetOut(originalOut); }
            }

            if (!built)
            {
                Debug.LogError($"[BUILD FAILED] After {maxRetries} attempts, no AAB was produced.");
                return;
            }
        }
        else if (platform == "ios")
        {
            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.iOS, BuildTarget.iOS);
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.iOS, ScriptingImplementation.IL2CPP);

            PlayerSettings.iOS.buildNumber = "0";
            PlayerSettings.bundleVersion = versionName;

            var outputPath = OutputPathAssign(currentOS, true, shortEnvId, versionName, note);
            var fullPath = outputPath;

            var buildPlayerOptions = new BuildPlayerOptions
            {
                scenes = GetEnabledScenes(),
                locationPathName = fullPath,
                target = BuildTarget.iOS,
                options = BuildOptions.None
            };

            var report = BuildPipeline.BuildPlayer(buildPlayerOptions);
            var summary = report.summary;
            
            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);

            if (summary.result == BuildResult.Succeeded)
                Debug.Log($"[BUILD SUCCESS!] Test Build succeeded: {summary.totalSize / 1_000_000f:F2} MB → {fullPath}");
            else
            {
                Debug.LogError($"[BUILD FAILED!] Build result: {summary.result}");
                foreach (var step in report.steps)
                {
                    foreach (var msg in step.messages)
                    {
                        if (msg.type == LogType.Error)
                            Debug.LogError($"[ERROR] {msg.content}");
                    }
                }
            } 
        }
    }

    public static void RemoteAndroidBothBuild()
    {
        var envId = MethodParamsForExternal("--value1");
        var version = MethodParamsForExternal("--value2");
        var note = MethodParamsForExternal("--value3");
        var pushToCloudVal = MethodParamsForExternal("--value4");
        var pushToCloud = pushToCloudVal == "1";
        var cloudApiKey = MethodParamsForExternal("--value5");
        var orgsId = MethodParamsForExternal("--value6");
        var projectId = MethodParamsForExternal("--value7");
        var envBucketId = MethodParamsForExternal("--value8");
        var currentOS = MethodParamsForExternal("--value9");
        var playerPrefsJson = MethodParamsForExternal("--value10");
        var buildType = MethodParamsForExternal("--value11").Trim().ToLowerInvariant();
        var platform = MethodParamsForExternal("--value12").Trim().ToLowerInvariant();
        var shortEnvId = MethodParamsForExternal("--value13");
        if (pushToCloud)
        {
            /*ccdApiUrl = $"https://services.api.unity.com/ccd/organizations/{orgsId}/projects/{projectId}/buckets";
            listUrl = $"https://services.api.unity.com/ccd/organizations/{orgsId}/projects/{projectId}/buckets/{bucketId}/releases/{relId}/entries";*/
            Debug.Log(pushToCloudVal+"\n"+cloudApiKey+"\n"+orgsId+"\n"+projectId+"\n"+envBucketId+"\n"+platform+"\n");
            return;
        }
        
        EditorPrefs.SetInt("UnityEditor.AssetImportWorkers", SystemInfo.processorCount);
        EditorPrefs.SetBool("CacheServerEnabled", true);
        EditorPrefs.SetString("CacheServerMode", "Local");
        PlayerSettings.stripEngineCode = true;
        if (platform == "android")
        {
            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            CompilationPipeline.RequestScriptCompilation();
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel22;
            PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel35;
            PlayerSettings.SetManagedStrippingLevel(BuildTargetGroup.Android, ManagedStrippingLevel.Low);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARMv7 | AndroidArchitecture.ARM64;
            PlayerSettings.Android.useCustomKeystore = true;
            PlayerSettings.Android.useAPKExpansionFiles = false;
            
            EditorUserBuildSettings.androidBuildSystem = AndroidBuildSystem.Gradle;

            var buildPlayerOptions = new BuildPlayerOptions();
            var fullPath = "";
            var outputPath = "";
            
            if (buildType == "apk")
            {
                outputPath = OutputPathAssign(currentOS, false, shortEnvId, version, note);
                if (File.Exists(outputPath)) File.Delete(outputPath);
                if (!Directory.Exists(outputPath)) Directory.CreateDirectory(outputPath);
                
                EditorUserBuildSettings.allowDebugging = true;
                EditorUserBuildSettings.connectProfiler = true;
                EditorUserBuildSettings.buildAppBundle = false;
                
                var apkName = $"ch-client-{shortEnvId}-{version}_{note}";
                fullPath = Path.Combine(outputPath, apkName);
                Directory.CreateDirectory(Path.GetDirectoryName(fullPath) ?? string.Empty);
                Debug.Log("Output Path: " + outputPath);
                Debug.Log("APK Name: " + apkName);
                Debug.Log("Full Path: " + fullPath);
                Debug.Log("Build App Bundle: " + EditorUserBuildSettings.buildAppBundle);
            }
            else if (buildType == "aab")
            {
                outputPath = OutputPathAssign(currentOS, false, shortEnvId, version, note);
                if (File.Exists(outputPath)) File.Delete(outputPath);
                if (!Directory.Exists(outputPath)) Directory.CreateDirectory(outputPath);
                                    
                EditorUserBuildSettings.buildAppBundle = true;
                
                var aabName = $"ch-client-{shortEnvId}-{version}_{note}";
                fullPath = Path.Combine(outputPath, aabName);
                Directory.CreateDirectory(Path.GetDirectoryName(fullPath) ?? string.Empty);
                Debug.Log("Output Path: " + outputPath);
                Debug.Log("AAB Name: " + aabName);
                Debug.Log("Full Path: " + fullPath);
                Debug.Log("Build App Bundle: " + EditorUserBuildSettings.buildAppBundle);
                Debug.Log($"[DEBUG] About to build: {buildPlayerOptions.locationPathName}");
            }
            
            CheckAndAddPlayerPrefLocal(playerPrefsJson);
            var keystoreInfo = GetPlayerPrefsKeys(playerPrefsJson);
            PlayerSettings.Android.keystoreName = keystoreInfo[0];
            PlayerSettings.Android.keystorePass = keystoreInfo[1];
            PlayerSettings.Android.keyaliasName = $"ch-ks-{shortEnvId}-upload-alias";
            PlayerSettings.Android.keyaliasPass = keystoreInfo[1];
            ScriptingDefineSymbolsHelper.SetKeystore(envId);
            
            if(PlayerSettings.Android.keystoreName != keystoreInfo[0])
                PlayerSettings.Android.keystoreName = keystoreInfo[0];
            if(PlayerSettings.Android.keystorePass != keystoreInfo[1])
                PlayerSettings.Android.keystorePass = keystoreInfo[1];
            if(PlayerSettings.Android.keyaliasName != $"ch-ks-{shortEnvId}-upload-alias")
                PlayerSettings.Android.keyaliasName = $"ch-ks-{shortEnvId}-upload-alias";
            if(PlayerSettings.Android.keyaliasPass != keystoreInfo[1])
                PlayerSettings.Android.keyaliasPass = keystoreInfo[1];
            
            var originalOut = Console.Out;
            Console.SetOut(TextWriter.Null);

            SetupPackageName(envId);
            ScriptingDefineSymbolsHelper.SetApplicationName(envId);
            ScriptingDefineSymbolsHelper.SetAppIcon(envId);
            BuildReport report = null;
            var scenes = GetEnabledScenes();
            if (scenes == null || scenes.Length == 0)
            {
                Debug.LogError("[BUILD ERROR] No scenes enabled in build settings.");
                return;
            }
            try {                     
                report = BuildPipeline.BuildPlayer(
                    scenes,
                    fullPath,
                    BuildTarget.Android,
                    BuildOptions.AcceptExternalModificationsToPlayer
                ); 
            }
            catch (IOException ioEx) { Debug.LogError($"[BUILD FAILED - IO ERROR] IOException during build: {ioEx.Message}"); return; }
            catch (Exception ex) { Debug.LogError($"[BUILD FAILED - EXCEPTION] Unexpected error during build: {ex.Message}"); return; }
            finally { Console.SetOut(originalOut); }
            var summary = report.summary;

            if (summary.result == BuildResult.Succeeded)
            {
                Debug.Log($"[BUILD SUCCESS!] Build succeeded: {summary.totalSize / 1_000_000f:F2} MB → {fullPath}");
                if (!File.Exists(fullPath))
                {
                    Debug.LogWarning("[WARNING] .aab not found at expected path after successful build. Attempting fallback...");
                    var candidates = Directory.GetFiles(outputPath, "*.aab", SearchOption.AllDirectories);
                    if (candidates.Length > 0)
                    {
                        var fallback = candidates.First();
                        File.Copy(fallback, fullPath, overwrite: true);
                        Debug.Log($"[INFO] Fallback .aab copied to expected path: {fullPath}");
                    }
                    else
                    {
                        Debug.LogError("[ERROR] No .aab file found even after fallback.");
                    }
                }
            }
            else
            {
                Debug.LogError($"[BUILD FAILED!] Build result: {summary.result}");
                foreach (var step in report.steps)
                {
                    foreach (var msg in step.messages)
                    {
                        if (msg.type == LogType.Error)
                            Debug.LogError($"[ERROR] {msg.content}");
                    }
                }
            }
        }
        else if (platform == "ios")
        {
            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.iOS, BuildTarget.iOS);
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.iOS, ScriptingImplementation.IL2CPP);
            var setBundleVersion = version.Split("-")[1];

            PlayerSettings.iOS.buildNumber = "0";
            PlayerSettings.bundleVersion = setBundleVersion;

            var outputPath = OutputPathAssign(currentOS, true, shortEnvId, version, note);
            var fullPath = outputPath;

            var buildPlayerOptions = new BuildPlayerOptions
            {
                scenes = GetEnabledScenes(),
                locationPathName = fullPath,
                target = BuildTarget.iOS,
                options = BuildOptions.None
            };

            var report = BuildPipeline.BuildPlayer(buildPlayerOptions);
            var summary = report.summary;

            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);
            
            if (summary.result == BuildResult.Succeeded)
                Debug.Log($"[BUILD SUCCESS!] Public Build succeeded: {summary.totalSize / 1_000_000f:F2} MB → {fullPath}");
            else
            {
                Debug.LogError($"[BUILD FAILED!] Build result: {summary.result}");
                foreach (var step in report.steps)
                {
                    foreach (var msg in step.messages)
                    {
                        if (msg.type == LogType.Error)
                            Debug.LogError($"[ERROR] {msg.content}");
                    }
                }
            } 
        }
    }
    
    private static void AndroidBuild(bool isTestBuild)
    {
        AddressableAssetSettings.CleanPlayerContent();
        AddressableAssetSettings.BuildPlayerContent();
        var settings = AddressableAssetSettingsDefaultObject.Settings;
        /*var sourcePath = settings.RemoteCatalogBuildPath.GetValue(settings);
        var targetPath = settings.RemoteCatalogLoadPath.GetValue(settings);
        var platform = BuildTarget.Android; 
        var bundleOutput = Path.Combine("Library/com.unity.addressables/aa", platform.ToString());
        var destination = Path.Combine(Application.streamingAssetsPath, "aa", platform.ToString());
        if (Directory.Exists(destination))
            Directory.Delete(destination, true);
        FileUtil.CopyFileOrDirectory(bundleOutput, destination);*/
        
        var env = GetEnvironment(false);
        if (env.Equals(""))
        {
            EditorUtility.DisplayDialog(
                "REMINDER",
                "Please setup your environment and try again",
                "Ok"
            );
            return;
        }
        
        InputPopupWindow.SetEnvironment(env);
        
        var buildAppBundle = isTestBuild 
            ? EditorUserBuildSettings.buildAppBundle = false 
            : EditorUserBuildSettings.buildAppBundle = true;
        
        var bundleVersionCode = isTestBuild
            ? PlayerSettings.Android.bundleVersionCode = 1
            : PlayerSettings.Android.bundleVersionCode++;
        
        PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.IL2CPP);
        PlayerSettings.stripEngineCode = true;
        PlayerSettings.SetManagedStrippingLevel(BuildTargetGroup.Android, ManagedStrippingLevel.Low);
        PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARMv7 | AndroidArchitecture.ARM64;
        PlayerSettings.Android.useCustomKeystore = true;
        EditorUserBuildSettings.development = false;
        EditorUserBuildSettings.androidBuildSystem = AndroidBuildSystem.Gradle;
        
        var envShort = GetEnvironment(true);
        if (envShort.Equals(""))
        {
            EditorUtility.DisplayDialog(
                "WARNING!",
                "Your current environment name is null or empty please try again.", 
                "OK"
            );
            return;
        }
        
        ScriptingDefineSymbolsHelper.SetKeystore(env);
        PlayerSettings.Android.keyaliasName = $"ch-ks-{envShort}-upload-alias";
        
        PlayerSettings.Android.useAPKExpansionFiles = false;
        
        InputPopupWindow.ShowWindow(
            onSubmit: (version, note) =>
            {
                var environmentConfirmAction = EditorUtility.DisplayDialog(
                    "Confirm Action",
                    "Your current environment is " + env + " do you want to proceed?",
                    "Yes", "No"
                );

                if (!environmentConfirmAction) return;
                
                var currentOS = SystemInfo.operatingSystem.Contains("Mac") ? "Darwin" : "Windows";
                var OutputPath = OutputPathAssign(currentOS, false, envShort, version, note);
                if (!Directory.Exists(OutputPath))
                    Directory.CreateDirectory(OutputPath);

                var apkName = $"ch-client-{envShort}-{version}{note}";
                var fullPath = Path.Combine(OutputPath, apkName);

                var deviceId = "";
                if (isTestBuild)
                {
                    deviceId = FindAndConnectWithDevice();
                    var install = new Process();
                    install.StartInfo.FileName = PlayerPrefs.GetString("ADB_PATH");
                    install.StartInfo.Arguments = $"-s {deviceId} install -r \"{fullPath}\"";
                    install.StartInfo.UseShellExecute = false;
                    install.Start();
                    install.WaitForExit();
                    Debug.Log(deviceId);
                }

                var buildPlayerOptions = new BuildPlayerOptions
                {
                    scenes = GetEnabledScenes(),
                    locationPathName = fullPath,
                    target = BuildTarget.Android,
                    options = BuildOptions.AcceptExternalModificationsToPlayer
                };
    
                var report = BuildPipeline.BuildPlayer(buildPlayerOptions);
                var summary = report.summary;

                if (summary.result == BuildResult.Succeeded)
                {
                    Debug.Log($"Build succeeded: {summary.totalSize / 1_000_000f:F2} MB → {fullPath}");

                    if (!isTestBuild || deviceId.Equals("")) return;
                    
                    var packageName = $"jp.okakichi.heroes.{envShort}";
                    var launch = new Process();
                    launch.StartInfo.FileName = PlayerPrefs.GetString("ADB_PATH");
                    launch.StartInfo.Arguments = $"-s {deviceId} install {packageName}";
                    launch.StartInfo.UseShellExecute = false;
                    launch.Start();
                    launch.WaitForExit();
                }
                else
                    Debug.LogError($"Build failed: {summary.result}");
                
                InputPopupWindow.CloseWindow();
            },
            onCancel: () =>
            {
                return; 
            });
    }
    //Unity Build Helper - END
    
    //Unity Build in button editor - START
    [MenuItem("Tools/Build/Build Helper/Android/Test Build")]
    public static void AndroidTestBuild() => AndroidBuild(true);
    
    [MenuItem("Tools/Build/Build Helper/Android/Public Build")]
    public static void AndroidPublicBuild() => AndroidBuild(false);
    
    [MenuItem("Tools/Build/Build Helper/Android/Both Build")]
    public static void AndroidBothBuild() => RemoteAndroidBothBuild();

    [MenuItem("Tools/Build/Build Helper/Test Addressable")]
    public static void AndroidTestAddressable() => AddPlayerPref();
    //Unity Build in button editor - END
}

public class InputPopupWindow : EditorWindow
{
    private static Action<string, string> _onSubmit;
    private static Action _onCancel;
    private string _versionText = "";
    private string _noteText = "";
    private static string _envText = "";
    private static InputPopupWindow _instanceWindow;

    public static void SetEnvironment(string env)
    {
        _envText = env;
    }

    public static void ShowWindow(Action<string, string> onSubmit, Action onCancel = null)
    {
        var window = ScriptableObject.CreateInstance<InputPopupWindow>();
        window.titleContent = new GUIContent("Build Helper");
        window.position = new Rect(Screen.width / 2.0f, Screen.height / 2.0f, 400, 500);
        _onSubmit = onSubmit;
        _onCancel = onCancel;
        window.ShowUtility();
    }

    private void OnGUI()
    {
        GUILayout.Space(15);

        GUILayout.BeginHorizontal();
        GUILayout.Space(15);

        GUILayout.BeginVertical();

        GUILayout.Space(10);
        GUILayout.Label($"Environment: {_envText}", EditorStyles.boldLabel);
        GUILayout.Space(10);

        GUILayout.Space(10);
        _versionText = EditorGUILayout.TextField("Version (*):", _versionText);
        GUILayout.Space(10);

        GUILayout.Space(10);
        _noteText = EditorGUILayout.TextField("Note (optional):", _noteText);
        GUILayout.Space(10);

        GUILayout.BeginHorizontal();

        GUILayout.Space(10);
        var guiEnabler = (_versionText.Equals("")) ? GUI.enabled = false : GUI.enabled = true;
        if (GUILayout.Button("Build"))
        {
            _versionText = GUILayout.TextField(_versionText);
            _noteText = GUILayout.TextField("_" + _noteText);
            _onSubmit?.Invoke(_versionText, _noteText);
            Close();
        }

        GUILayout.Space(20);

        GUI.enabled = true;
        if (GUILayout.Button("Cancel"))
        {
            _onCancel?.Invoke();
            Close();
        }

        GUILayout.EndHorizontal();

        GUILayout.EndVertical();

        GUILayout.Space(15);
        GUILayout.EndHorizontal();

        GUILayout.Space(15);
    }

    private void OnDestroy()
    {
        _onSubmit = null;
        _onCancel = null;
        _instanceWindow = null;
    }

    public static void CloseWindow()
    {
        if (_instanceWindow != null)
        {
            _instanceWindow.Close();
            _instanceWindow = null;
        }
    }
}
#endif

#if UNITY_ANDROID
public static class KeystoreAliasSelector
{
    public static void SelectFirstAlias()
    { 
        var keystore = PlayerSettings.Android.keystoreName;
        var storePass = PlayerSettings.Android.keystorePass;
        if (string.IsNullOrEmpty(keystore) || string.IsNullOrEmpty(storePass))
        {
            Debug.LogWarning("[KeystoreAliasSelector] Empty keystore path or password; skipping alias selection.");
            return;
        }

        if (!File.Exists(keystore))
        {
            Debug.LogError($"[KeystoreAliasSelector] Keystore not found at path:\n    {keystore}\nPlease verify the path is correct.");
            return;
        }

        var jdkRoot = AndroidExternalToolsSettings.jdkRootPath;
        if (string.IsNullOrEmpty(jdkRoot) || !Directory.Exists(jdkRoot))
            jdkRoot = Environment.GetEnvironmentVariable("JAVA_HOME") ?? "";
        var exeName = Application.platform == RuntimePlatform.WindowsEditor ? "keytool.exe" : "keytool";

        string[] candidates = {
            Path.Combine(jdkRoot, "bin", exeName),
            exeName
        };

        foreach (var keytoolPath in candidates)
        {
            if (keytoolPath != exeName && !File.Exists(keytoolPath))
                continue;

            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName               = keytoolPath,
                    Arguments              = $"-list -v -keystore \"{keystore}\" -storepass \"{storePass}\"",
                    RedirectStandardOutput = true,
                    RedirectStandardError  = true,
                    UseShellExecute        = false,
                    CreateNoWindow         = true
                };

                using var proc = Process.Start(psi);
                if (proc == null)
                    throw new Exception("Failed to start keytool process.");

                string stdout = proc.StandardOutput.ReadToEnd();
                string stderr = proc.StandardError.ReadToEnd();
                proc.WaitForExit();

                if (proc.ExitCode != 0)
                {
                    Debug.LogWarning(
                        $"[KeystoreAliasSelector] keytool at '{keytoolPath}' exited {proc.ExitCode}.\n" +
                        $"--- STDOUT ---\n{stdout}\n--- STDERR ---\n{stderr}"
                    );
                    continue;
                }

                var match = Regex.Match(stdout, @"Alias\s+name:\s*(\S+)");
                if (!match.Success)
                {
                    Debug.LogError(
                        $"[KeystoreAliasSelector] No aliases found (using keytool at '{keytoolPath}').\n" +
                        $"Full output:\n{stdout}"
                    );
                    return;
                }

                var firstAlias = match.Groups[1].Value;
                PlayerSettings.Android.keyaliasName = firstAlias;
                Debug.Log($"[KeystoreAliasSelector] Selected alias '{firstAlias}' from '{keytoolPath}'.");

                AssetDatabase.SaveAssets();
                AssetDatabase.Refresh(ImportAssetOptions.ForceUpdate);
                return;
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[KeystoreAliasSelector] Error invoking keytool at '{keytoolPath}': {ex.Message}");
            }
        }

        Debug.LogError("[KeystoreAliasSelector] All keytool attempts failed. Check your keystore path, password, and that keytool is accessible.");
    }
}
#endif

#if UNITY_EDITOR
[InitializeOnLoad]
public static class BuildEnforcer
{
    private const string CompanyName = "Okakichi.co.jp";
    private const string ProductName = "Changokushi! Heroes";
    private static int _versionCode;
    private static string _env;

    static BuildEnforcer()
    {
        Enforce();
        playModeStateChanged += OnPlayModeChanged;
    }
    
    private static void OnPlayModeChanged(PlayModeStateChange state)
    {
        if (state is PlayModeStateChange.EnteredEditMode or PlayModeStateChange.EnteredPlayMode)
        {
            Enforce();
        }
    }

    private static void Enforce()
    {
        var basePackage = "jp.okakichi.heroes";
        var buildTarget = NamedBuildTarget.FromBuildTargetGroup(EditorUserBuildSettings.selectedBuildTargetGroup);

        #if PRODUCTION_ENV
        EditorPrefs.SetString("CURRENT_ENV", "PRODUCTION_ENV");
        PlayerSettings.SetApplicationIdentifier(buildTarget, basePackage);
        #elif STAGING_ENV
        EditorPrefs.SetString("CURRENT_ENV", "STAGING_ENV");
        PlayerSettings.SetApplicationIdentifier(buildTarget, basePackage + ".staging");
        #elif DEVELOP_ENV
        EditorPrefs.SetString("CURRENT_ENV", "DEVELOP_ENV");
        PlayerSettings.SetApplicationIdentifier(buildTarget, basePackage + ".dev");
        #elif QA_ENV
        EditorPrefs.SetString("CURRENT_ENV", "QA_ENV");
        PlayerSettings.SetApplicationIdentifier(buildTarget, basePackage + ".qa");
        #endif
        
        PlayerPrefs.Save();
        _env = EditorPrefs.GetString("CURRENT_ENV");
        
        PlayerSettings.productName = ProductName;
        PlayerSettings.companyName = CompanyName;
        PlayerSettings.Android.minSdkVersion    = AndroidSdkVersions.AndroidApiLevel22;
        PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel35;
        PlayerSettings.Android.useCustomKeystore = true;
        
        _versionCode = PlayerPrefs.GetInt("VersionCode");
        PlayerSettings.Android.bundleVersionCode = _versionCode;

        ScriptingDefineSymbolsHelper.SetApplicationName(_env);
        ScriptingDefineSymbolsHelper.SetAppIcon(_env);

        ScriptingDefineSymbolsHelper.SetKeystore(_env);
        #if UNITY_ANDROID
        KeystoreAliasSelector.SelectFirstAlias();  
        #endif

        var bucket = _env switch
        {
            "PRODUCTION_ENV" => "production",
            "STAGING_ENV" => "staging",
            "QA_ENV" => "qa",
            "DEVELOP_ENV" => "develop",
            _ => _env.ToLowerInvariant().Replace("_env", "")
        };
        BuildAddressables.GetSettingsObject();
        BuildAddressables.SetProfile(bucket);
        
        var so = new SerializedObject(
             AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/EditorSettings.asset")[0]
        );
        var prop = so.FindProperty("AndroidBuildSystem");
        if (prop != null)
        {
            prop.intValue = 1;
            so.ApplyModifiedProperties();
        }
        else
            Debug.LogWarning("[BuildEnforcer] 'AndroidBuildSystem' not found; skipping.");
        
        var aa = AddressableAssetSettingsDefaultObject.Settings;
        if (aa == null)
            Debug.LogError("[BuildEnforcer] Could not find AddressableAssetSettings!");
        else
        {
            var newId = aa.profileSettings.GetProfileId(bucket);
            if (string.IsNullOrEmpty(newId))
                Debug.LogError($"[BuildEnforcer] No Addressables profile named '{_env}'.");
            else if (aa.activeProfileId != newId)
            {
                aa.activeProfileId = newId;
                EditorUtility.SetDirty(aa);
                AssetDatabase.SaveAssets();
                Debug.Log($"[BuildEnforcer] Addressables profile set to '{_env}'.");
            }
        }
        
        foreach (BuildTargetGroup g in Enum.GetValues(typeof(BuildTargetGroup)))
        {
            if (g == BuildTargetGroup.Unknown) continue;
            try
            {
                var defs = PlayerSettings
                    .GetScriptingDefineSymbolsForGroup(g)
                    .Split(';')
                    .Where(s => !s.EndsWith("_ENV"))
                    .ToList();
                defs.Add(_env);
                PlayerSettings.SetScriptingDefineSymbolsForGroup(g, string.Join(";", defs));
            }
            catch (ArgumentException)
            {
                Debug.Log($"[BuildEnforcer] Skipping unsupported group: {g}");
            }
        }
         
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh(ImportAssetOptions.ForceUpdate);
    }

    public class PreBuild : IPreprocessBuildWithReport
    {
        public int callbackOrder => 0;

        public void OnPreprocessBuild(BuildReport report)
        {
            Enforce();
        }
    }

    public class PostBuild : IPostprocessBuildWithReport
    {
        public int callbackOrder => 0;

        public void OnPostprocessBuild(BuildReport report)
        {
            Enforce();
        }
    }

    [InitializeOnLoadMethod]
    private static void EnforceOnLoad()
    {
        Enforce();
        playModeStateChanged += (state) =>
        {
            if (state is PlayModeStateChange.EnteredEditMode or PlayModeStateChange.EnteredPlayMode)
            {
                Enforce();
            }
        };
    }

    [DidReloadScripts]
    public static void OnScriptsReloaded()
    {
        Enforce();
    }
}
#endif