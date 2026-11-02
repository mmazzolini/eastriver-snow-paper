// Where the page reads its data. On GitHub Pages the data files sit next to the page in data/ (copied
// there by the site's deploy workflow). For a local copy, link or copy the data files into docs/data/
// (the data record's website_data/ folder) and serve docs/ (python -m http.server).
window.SITE_CONFIG = {
  url: (name) => `./data/${name}`,
  downloads: true,                          // figure PNG download
  hashState: true,                          // keep the view in the URL (#...) for sharing
};
