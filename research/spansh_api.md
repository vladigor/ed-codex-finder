You are looking for the API that powers the bulk Spansh Body Search Tool (where you search for multiple celestial bodies filtering by atmosphere, materials, gravity, distance, etc.), rather than retrieving a single body by its ID. [1] (https://spansh.co.uk/bodies)Yes, the bulk search API exists, but because of how massive the data queries are, Spansh handles searches using an asynchronous job queue.To use the Spansh Bodies Search programmatically, you have to hit two endpoints in succession: [1] (https://www.reddit.com/r/EliteDangerous/comments/1josg7t/where_can_i_find_a_good_documentation_for_spansh/)Step 1: Initiate the Search (POST)You must send an HTTP POST request containing your search parameters (filters, sorting, reference system) to the search endpoint. [1] (https://www.reddit.com/r/EliteDangerous/comments/1josg7t/where_can_i_find_a_good_documentation_for_spansh/)Endpoint: https://spansh.co.ukContent-Type: application/jsonExample Payload:json{
  "reference_system": "Sol",
  "distance": {
    "min": 0,
    "max": 100
  },
  "atmosphere": ["Oxygen"],
  "filters": {
    "landable": {
      "value": "1"
    }
  },
  "sort": [
    {
      "distance": "asc"
    }
  ],
  "size": 50,
  "page": 1
}
Use code with caution.The Response: Spansh will not return the results immediately. Instead, it will return a unique Job ID (a UUID string), like this:json{
  "job": "4F9829F6-B82E-11E7-9704-9472C33B8412"
}
Use code with caution. [1] (https://www.reddit.com/r/EliteDangerous/comments/1josg7t/where_can_i_find_a_good_documentation_for_spansh/)Step 2: Fetch the Results (GET)Once you have the job UUID, you must poll or query the results endpoint using an HTTP GET request: [1] (https://www.reddit.com/r/EliteDangerous/comments/1josg7t/where_can_i_find_a_good_documentation_for_spansh/)Endpoint: https://spansh.co.uk{job_id}Example URL: https://spansh.co.ukIf the job is still processing, the API status will indicate it is queued. Once finished, it will return the complete JSON array of matching planets or stars fitting your search parameters.💡 Pro-Tip for Constructing PayloadsBecause the Spansh Body Search contains hundreds of different filter combinations (rings, belt filters, materials, volcanism), the absolute easiest way to build your API payload is to: [1] (https://spansh.co.uk/bodies)Go to the web-based Spansh Body Search UI.Open your browser's Developer Tools (F12) and navigate to the Network tab.Click "Search" on the website and look for the network request made to /api/bodies/search.You can right-click it and select "Copy as fetch" or "Copy Object" to perfectly replicate the JSON parameters for your own script! [1] (https://www.reddit.com/r/EliteDangerous/comments/1josg7t/where_can_i_find_a_good_documentation_for_spansh/), [2] (https://spansh.co.uk/bodies)(Note: Please ensure you rate-limit your requests to no more than 1 per second to avoid overtaxing the public server.) [1] (https://www.reddit.com/r/EliteDangerous/comments/1josg7t/where_can_i_find_a_good_documentation_for_spansh/)Would you like me to generate a Python or JavaScript code script that handles both the POST request, polls for the results, and handles the rate limiting for you?