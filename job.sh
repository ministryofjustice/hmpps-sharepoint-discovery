#!/bin/bash
db_job=/tmp/dbjob.yaml

items_to_delete=(".metadata.uid" ".metadata.resourceVersion" ".metadata.creationTimestamp" ".status" ".spec.template.metadata.labels" ".spec.selector")
for each_del in "${items_to_delete[@]}"; do
  yq eval "del(${each_del})" -i ${db_job}
done
unique_name="sc-test-$(date +%s)"
yq eval ".metadata.name = \"${unique_name}\"" -i ${db_job}
yq eval '.spec.template.spec.containers[0].command = ["/usr/bin/sleep", "15000"]' -i ${db_job}

kubectl -n hmpps-portfolio-management-prod apply -f ${db_job}
kubectl get pods  | grep sc-test | grep Running
