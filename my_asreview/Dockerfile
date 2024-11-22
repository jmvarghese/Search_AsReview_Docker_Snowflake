FROM ghcr.io/asreview/asreview:v1.6.3

RUN pip install --no-cache-dir sentence-transformers \
    && pip install --no-cache-dir requests==2.27.1 \
    && pip uninstall -y keras \
    && pip install --no-cache-dir tf-keras==2.16.0 --no-dependencies \
    && pip install --no-cache-dir tensorflow-cpu==2.16.1

# Set environment variables
ENV ASREVIEW_CONFIG_FILE=/app/asreview_config.toml
ENV ASREVIEW_CONF_FILE=/app/asreview.conf

# Expose the ports that the app runs on
EXPOSE 5000

# Command to run the application
CMD ["asreview", "lab"]
