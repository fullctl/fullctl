export default [
  {
    files: ["**/*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "script",
      globals: {
        // Browser globals
        window: "readonly",
        document: "readonly",
        console: "readonly",
        setTimeout: "readonly",
        setInterval: "readonly",
        clearTimeout: "readonly",
        clearInterval: "readonly",
        alert: "readonly",
        confirm: "readonly",
        history: "readonly",
        location: "readonly",
        navigator: "readonly",
        URL: "readonly",
        URLSearchParams: "readonly",
        fetch: "readonly",
        FormData: "readonly",
        FileReader: "readonly",
        Blob: "readonly",
        Event: "readonly",
        CustomEvent: "readonly",
        MutationObserver: "readonly",
        HTMLElement: "readonly",

        // jQuery
        $: "readonly",
        jQuery: "readonly",

        // twentyc libraries
        twentyc: "readonly",
        $tc: "readonly",
        $ctl: "readonly",

        // fullctl application globals
        fullctl: "writable",
        aaactl_user_info: "readonly",
        account: "writable",
        grainy: "readonly",
      },
    },
    rules: {
      "no-unused-vars": "warn",
      "no-undef": "warn",
    },
  },
];
