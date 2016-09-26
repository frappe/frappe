

<p>Frappe handles failure of jobs in the following way,</p><p>1) If a job fails, (raises exception), it's logged in Scheduler Log and&nbsp; <code>logs/worker.error.log</code>.<br>2) Keeps a lock file and would not run anymore if lock file is there.<br>3) Raises LockTimeoutError in case the lock file is more than 10 minutes old.</p>

<p>You can configure email notification for scheduler errors. By writing a file, <code>sites/common_site_config.json</code> with content<br></p>

<pre><code class="json hljs">{
  "<span class="hljs-attribute">celery_error_emails</span>": <span class="hljs-value">{
    "<span class="hljs-attribute">ADMINS</span>": <span class="hljs-value">[
      [
        <span class="hljs-string">"Person 1"</span>,
        <span class="hljs-string">"person1@example.com"</span>
      ],
      [
        <span class="hljs-string">"Person2 "</span>,
        <span class="hljs-string">"person2@example.com"</span>
      ]
    ]</span>,
    "<span class="hljs-attribute">SERVER_EMAIL</span>": <span class="hljs-value"><span class="hljs-string">"exceptions@example.com"</span>
  </span>}
</span>}</code></pre>

<p>One limitation is that it'll use local mailserver on port 25 to send the emails.</p>