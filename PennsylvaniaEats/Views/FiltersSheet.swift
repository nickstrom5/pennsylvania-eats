import SwiftUI

struct FiltersSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State private var townSearch = ""

    var body: some View {
        @Bindable var model = model
        NavigationStack {
            Form {
                Section("Region") {
                    Picker("Region", selection: Binding(get: { model.filters.region }, set: { r in
                        model.filters.region = r
                        if let t = model.filters.town, let r, model.townRegions[t] != r { model.filters.town = nil }
                    })) {
                        Text("All of Pennsylvania").tag(String?.none)
                        ForEach(model.regions, id: \.self) { r in Text(r).tag(String?.some(r)) }
                    }
                }
                Section("City or town") {
                    NavigationLink {
                        townPicker
                    } label: {
                        HStack {
                            Text("Place"); Spacer()
                            Text(model.filters.town ?? "All of \(model.filters.region ?? "Pennsylvania")").foregroundStyle(Theme.muted)
                        }
                    }
                }
                Section("Cuisine") {
                    Picker("Cuisine", selection: $model.filters.cuisine) {
                        Text("All cuisines").tag(String?.none)
                        ForEach(model.cuisines, id: \.name) { c in Text("\(c.name) (\(c.count.formatted()))").tag(String?.some(c.name)) }
                    }
                }
                Section {
                    Toggle("Hide chains (5+ locations)", isOn: $model.filters.hideChains)
                    Toggle("Only licensed, high-confidence or hand-checked places", isOn: $model.filters.confirmedOnly)
                    Toggle("Include non-restaurants", isOn: $model.filters.includeNonRestaurants)
                } footer: {
                    Text("That means on an official list (a Philadelphia food license or an Allegheny County permit), a high-confidence map listing, or hand-checked by us. Non-restaurants are convenience and grocery counters, members-only clubs, stadium and campus dining and the like.")
                }
                if model.filters.activeCount > 0 {
                    Section { Button("Clear all filters", role: .destructive) { model.filters = Filters() } }
                }
            }
            .navigationTitle("Filters")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }
        .presentationDetents([.medium, .large])
    }

    private var townPicker: some View {
        let q = Search.normalize(townSearch)
        let towns = model.towns.filter { (model.filters.region == nil || model.townRegions[$0.name] == model.filters.region)
            && (q.isEmpty || (" " + Search.normalizeAddress($0.name)).contains(" " + Search.normalizeAddress(q))) }
        return List {
            Button { model.filters.town = nil } label: {
                HStack { Text("All of \(model.filters.region ?? "Pennsylvania")"); Spacer(); if model.filters.town == nil { Image(systemName: "checkmark") } }
            }
            ForEach(towns, id: \.name) { t in
                Button { model.filters.town = t.name } label: {
                    HStack {
                        Text(t.name).foregroundStyle(Theme.ink)
                        Spacer()
                        Text(t.count.formatted()).foregroundStyle(Theme.muted).monospacedDigit()
                        if model.filters.town == t.name { Image(systemName: "checkmark").foregroundStyle(Theme.navy) }
                    }
                }
            }
        }
        .searchable(text: $townSearch, prompt: "Find a city or town")
        .navigationTitle("Place")
    }
}
